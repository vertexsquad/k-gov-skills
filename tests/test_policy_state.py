from __future__ import annotations

import multiprocessing
import sqlite3
import tempfile
import threading
import unittest
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, date, datetime
from email.utils import format_datetime
from pathlib import Path
from typing import Protocol
from unittest.mock import patch
from urllib.request import Request

from kgov_runtime.http import HttpPolicyEnforcer, HttpTransport, ReadOnlyHttpError, SourceRequest
from kgov_runtime.policy_state import (PolicyDigest, PolicyDigestMismatchError, PolicyConfigurationError, PolicyId, PolicyKey, PolicyState, PolicyStateUnavailableError, RatePolicy, RetryAfterError, RobotsEntry, WaitLimitExceededError)
from kgov_runtime.source_policy import SourcePolicyRegistry
from tests.test_read_only_http import OPERATION, Response, reviewed_catalog


class FakeTime:
    def __init__(self, now: float) -> None:
        self.now = now
        self.waits: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


class Barrier(Protocol):
    def wait(self, timeout: float | None = None) -> int: ...


class ResultQueue(Protocol):
    def put(self, value: float | str) -> None: ...


POLICY_ID = PolicyId("fixture-policy")
DIGEST = PolicyDigest("a" * 64)
OTHER_DIGEST = PolicyDigest("b" * 64)


def rate_policy(*, digest: PolicyDigest = DIGEST, maximum: float = 120.0) -> RatePolicy:
    return RatePolicy(PolicyKey(POLICY_ID, digest), 2, 60.0, 1, maximum)


def concurrent_reserve(path: str, barrier: Barrier, queue: ResultQueue) -> None:
    state = PolicyState(Path(path), clock=lambda: 100.0, sleeper=lambda _seconds: None)
    barrier.wait(timeout=5.0)
    try:
        queue.put(state.reserve(rate_policy()).wait_seconds)
    except PolicyStateUnavailableError:
        queue.put("unavailable")


class PolicyStateContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "policy.sqlite3"
        self.time = FakeTime(100.0)
        self.state = PolicyState(self.path, clock=self.time.clock, sleeper=self.time.sleep)

    def test_gcra_reserves_exact_wait_for_two_per_minute_with_burst_one(self) -> None:
        # Given: a fresh 2 requests / 60 seconds, burst 1 budget
        policy = rate_policy()
        # When: two calls reserve against the same policy
        first = self.state.reserve(policy)
        second = self.state.reserve(policy)
        # Then: the second call waits exactly one 30-second emission interval
        self.assertEqual(((0.0, 30.0), [30.0]), ((first.wait_seconds, second.wait_seconds), self.time.waits))

    def test_open_rechecks_cooldown_committed_during_reservation_sleep(self) -> None:
        # Given: two real state instances share a consumed budget and clock.
        policy = rate_policy()
        self.state.reserve(policy)

        def sleep(seconds: float) -> None:
            if not self.time.waits:
                self.state.record_retry_after(policy, "90")
            self.time.sleep(seconds)

        contender = PolicyState(self.path, clock=self.time.clock, sleeper=sleep)
        # When: another connection commits a cooldown during the reserved wait.
        opened_at = contender.open(policy, self.time.clock)
        # Then: transmission waits for 190, without consuming a second slot.
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual((160.0, 190.0), connection.execute(
                "SELECT theoretical_arrival, blocked_until FROM rate_state"
            ).fetchone())
        self.assertEqual(190.0, opened_at)
        self.assertEqual([30.0, 60.0], self.time.waits)

    def test_open_counts_repeated_cooldowns_against_one_cumulative_cap(self) -> None:
        for maximum in (90.0, 89.0, 60.0):
            with self.subTest(maximum=maximum):
                # Given: each of the first two waits receives a later cooldown.
                self.state.purge()
                self.time.now, self.time.waits = 100.0, []
                policy = rate_policy(maximum=maximum)
                self.state.reserve(policy)
                opened: list[float] = []

                def sleep(seconds: float) -> None:
                    if len(self.time.waits) < 2:
                        self.state.record_retry_after(policy, "60")
                    self.time.sleep(seconds)

                contender = PolicyState(self.path, clock=self.time.clock, sleeper=sleep)
                # When: one open encounters multiple shared-state extensions.
                if maximum == 90.0:
                    contender.open(policy, lambda: opened.append(self.time.now))
                    self.assertEqual(([190.0], [30.0, 30.0, 30.0]), (opened, self.time.waits))
                else:
                    with self.assertRaises(WaitLimitExceededError) as raised:
                        contender.open(policy, lambda: opened.append(self.time.now))
                    self.assertEqual((90.0, maximum), (raised.exception.required_seconds, raised.exception.maximum_seconds))
                    self.assertEqual(([], [30.0, 30.0]), (opened, self.time.waits))
                # Then: both success and rejection retain exactly one reservation.
                with closing(sqlite3.connect(self.path)) as connection:
                    self.assertEqual((160.0, 190.0), connection.execute(
                        "SELECT theoretical_arrival, blocked_until FROM rate_state"
                    ).fetchone())

    def test_open_rechecks_both_digests_after_each_wait(self) -> None:
        for table in ("rate_state", "robots_state"):
            for replacement_wait in (0, 1):
                with self.subTest(table=table, replacement_wait=replacement_wait):
                    # Given: a second instance changes authority during a wait.
                    self.state.purge()
                    self.time.now, self.time.waits = 100.0, []
                    policy = rate_policy()
                    self.state.reserve(policy)

                    def sleep(seconds: float) -> None:
                        if len(self.time.waits) == replacement_wait:
                            self.state.purge(POLICY_ID)
                            if table == "rate_state":
                                self.state.reserve(rate_policy(digest=OTHER_DIGEST))
                            else:
                                self.state.store_robots(PolicyKey(POLICY_ID, OTHER_DIGEST), RobotsEntry(True, 300.0))
                        else:
                            self.state.record_retry_after(policy, "60")
                        self.time.sleep(seconds)

                    contender = PolicyState(self.path, clock=self.time.clock, sleeper=sleep)
                    # When / Then: stale authority cannot reach the opener.
                    with self.assertRaises(PolicyDigestMismatchError):
                        contender.open(policy, lambda: self.fail("opener called"))
                    self.assertEqual([30.0] * (replacement_wait + 1), self.time.waits)

    def test_open_without_cooldown_does_not_rereserve_or_hold_opener_lock(self) -> None:
        # Given: a pre-existing slot and a second connection used by the opener.
        policy = rate_policy()
        self.state.reserve(policy)
        contender = PolicyState(self.path, clock=self.time.clock, sleeper=self.time.sleep)
        opened: list[float] = []

        def opener() -> list[float]:
            self.state.record_retry_after(policy, "0")
            opened.append(self.time.now)
            return opened

        # When: the existing reservation wait completes without an extension.
        returned = contender.open(policy, opener)
        # Then: one opener preserves its result, and can write through SQLite.
        self.assertIs(opened, returned)
        self.assertEqual(([130.0], [30.0]), (opened, self.time.waits))
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual((160.0,), connection.execute("SELECT theoretical_arrival FROM rate_state").fetchone())

    def test_open_recheck_fails_closed_on_invalid_shared_cooldown(self) -> None:
        for value in ("invalid", float("inf")):
            with self.subTest(value=value):
                # Given: persisted cooldown corruption during the initial wait.
                self.state.purge()
                self.time.now, self.time.waits = 100.0, []
                policy = rate_policy()
                self.state.reserve(policy)

                def sleep(seconds: float) -> None:
                    with closing(sqlite3.connect(self.path)) as connection:
                        connection.execute("UPDATE rate_state SET blocked_until = ?", (value,))
                        connection.commit()
                    self.time.sleep(seconds)

                contender = PolicyState(self.path, clock=self.time.clock, sleeper=sleep)
                # When / Then: the post-sleep read cannot dispatch corrupt state.
                with self.assertRaises(PolicyStateUnavailableError):
                    contender.open(policy, lambda: self.fail("opener called"))

    def test_open_nonadvancing_sleeper_exhausts_cumulative_cap(self) -> None:
        # Given: a sleeper that returns without advancing the controlled clock.
        policy = rate_policy(maximum=60.0)
        self.state.record_retry_after(policy, "30")
        contender = PolicyState(self.path, clock=self.time.clock, sleeper=self.time.waits.append)
        # When / Then: repeated waits terminate at the cap, without an opener.
        with self.assertRaises(WaitLimitExceededError) as raised:
            contender.open(policy, lambda: self.fail("opener called"))
        self.assertEqual(90.0, raised.exception.required_seconds)
        self.assertEqual([30.0, 30.0], self.time.waits)

    def test_open_unrepresentable_wait_increment_fails_closed(self) -> None:
        # Given: a clock reset makes an extra wait too small to add to the total.
        policy = rate_policy(maximum=1e17)
        self.state.record_retry_after(policy, "10000000000000000")

        def sleep(seconds: float) -> None:
            self.time.waits.append(seconds)
            self.time.now = 0.0
            self.state.purge()
            self.state.record_retry_after(policy, "1")

        contender = PolicyState(self.path, clock=self.time.clock, sleeper=sleep)
        # When / Then: numerical loss cannot permit an unbounded recheck loop.
        with self.assertRaises(PolicyStateUnavailableError):
            contender.open(policy, lambda: self.fail("opener called"))
        self.assertEqual([1e16], self.time.waits)

    def test_http_rechecks_shared_state_before_robots_and_page_openers(self) -> None:
        for robots in ("required", "documented-api-exemption"):
            for maximum, replace_digest in ((90, False), (89, False), (90, True)):
                with self.subTest(robots=robots, maximum=maximum, replace_digest=replace_digest):
                    # Given: real registry, enforcer and SQLite; only transport/time are synthetic.
                    self.state.purge()
                    self.time.now, self.time.waits = 100.0, []
                    catalog = reviewed_catalog(robots=robots)
                    catalog["source_policies"][0]["rate_limit"].update(
                        requests=2, per_seconds=60, burst=1, max_wait_seconds=maximum
                    )
                    registry = SourcePolicyRegistry.from_catalog(catalog, on_date=date(2026, 9, 6))
                    selected = registry.policies[0]
                    policy = RatePolicy(PolicyKey(PolicyId(selected.id), PolicyDigest(selected.digest)), 2, 60.0, 1, maximum)
                    self.state.reserve(policy)
                    opened: list[tuple[str, float]] = []

                    def sleep(seconds: float) -> None:
                        if not self.time.waits:
                            if replace_digest:
                                self.state.purge(policy.key.policy_id)
                                self.state.store_robots(PolicyKey(policy.key.policy_id, OTHER_DIGEST), RobotsEntry(True, 300.0))
                            else:
                                self.state.record_retry_after(policy, "90")
                        self.time.sleep(seconds)

                    def opener(request: Request, timeout: float) -> Response:
                        opened.append((request.full_url, self.time.now))
                        self.state.record_retry_after(policy, "0")
                        if request.full_url.endswith("/robots.txt"):
                            return Response(b"User-agent: *\nAllow: /", media_type="text/plain")
                        return Response(b"<title>Example</title>")

                    contender = PolicyState(self.path, clock=self.time.clock, sleeper=sleep)
                    enforcer = HttpPolicyEnforcer(registry, contender, HttpTransport(opener, lambda _host: ["1.1.1.1"]))
                    request = SourceRequest("https://www.example.go.kr/page", OPERATION, selected)
                    # When / Then: public HTTP API succeeds only after the block, or denies without transport.
                    if maximum == 90 and not replace_digest:
                        result = enforcer.fetch_text(request, lambda document: document.content_length)
                        self.assertEqual(22, result.value)
                        self.assertEqual(selected.digest, result.source_receipt.policy_digest)
                        paths = ["/robots.txt", "/page"] if robots == "required" else ["/page"]
                        self.assertEqual([("https://www.example.go.kr" + path, 190.0) for path in paths], opened)
                        self.assertEqual([30.0, 60.0], self.time.waits)
                    else:
                        with self.assertRaises(ReadOnlyHttpError) as raised:
                            enforcer.fetch_text(request, lambda document: document.content_length)
                        self.assertEqual("budget-exhausted", raised.exception.status)
                        self.assertEqual([], opened)
                        self.assertEqual([30.0], self.time.waits)

    def test_clock_rollback_does_not_create_budget(self) -> None:
        # Given: one reservation at timestamp 100
        self.state.reserve(rate_policy())
        self.time.now = 90.0
        # When: a rolled-back clock reserves again
        reservation = self.state.reserve(rate_policy())
        # Then: existing theoretical arrival time still controls the wait
        self.assertEqual(40.0, reservation.wait_seconds)

    def test_wait_over_cap_has_no_reservation_or_opener_call(self) -> None:
        # Given: a consumed budget whose next wait exceeds the caller cap
        policy = rate_policy(maximum=20.0)
        self.state.reserve(policy)
        opened: list[bool] = []
        # When: the caller asks the state gate to open once
        with self.assertRaises(WaitLimitExceededError):
            self.state.open(policy, lambda: opened.append(True))
        # Then: no opener or rejected reservation advances state
        self.assertEqual([], opened)
        self.time.now = 130.0
        self.assertEqual(0.0, self.state.reserve(policy).wait_seconds)

    def test_processes_serialize_competing_reservations(self) -> None:
        # Given: initialized state and two independently spawned callers
        self.state.purge()
        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(2)
        queue = context.Queue()
        processes = [
            context.Process(target=concurrent_reserve, args=(str(self.path), barrier, queue))
            for _ in range(2)
        ]
        results: list[float | str] = []
        # When: both processes reserve from the same SQLite file
        try:
            for process in processes:
                process.start()
            results = [queue.get(timeout=5.0) for _ in processes]
        finally:
            for process in processes:
                process.join(timeout=5.0)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5.0)
            queue.close()
            queue.join_thread()
        # Then: BEGIN IMMEDIATE yields one immediate and one deferred slot
        self.assertEqual([0.0, 30.0], sorted(results))
        self.assertTrue(all(process.exitcode == 0 for process in processes))

    def test_retry_after_delta_and_http_date_block_without_retrying(self) -> None:
        # Given: a response timestamp and two valid Retry-After representations
        self.time.now = 1_000.0
        policy = rate_policy()
        date_value = format_datetime(datetime.fromtimestamp(1_090.0, tz=UTC), usegmt=True)
        # When: delta then later HTTP-date state is recorded
        delta = self.state.record_retry_after(policy, "45")
        dated = self.state.record_retry_after(policy, date_value)
        reservation = self.state.reserve(policy)
        # Then: the latest server block is persisted and waited exactly once
        self.assertEqual(((45.0, 90.0, 90.0), [90.0]), ((delta, dated, reservation.wait_seconds), self.time.waits))

    def test_malformed_retry_after_fails_closed(self) -> None:
        # Given: malformed, unbounded, naive, and non-GMT server instructions
        values = ("tomorrow-ish", "９", "9" * 400, "Sun, 06 Nov 1994 08:49:37", "Sun, 06 Nov 1994 08:49:37 PST", "Sunday, 06-Nov-94 08:49:37 GMT")
        # When / Then: none can create persisted cooldown state
        for value in values:
            with self.subTest(value=value), self.assertRaises(RetryAfterError):
                self.state.record_retry_after(rate_policy(), value)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual((0,), connection.execute("SELECT count(*) FROM rate_state").fetchone())

    def test_retry_after_over_cap_blocks_future_opener(self) -> None:
        # Given: a server delay beyond the policy wait cap
        policy = rate_policy(maximum=20.0)
        self.state.record_retry_after(policy, "90")
        opened: list[bool] = []
        # When: another caller attempts to open
        with self.assertRaises(WaitLimitExceededError):
            self.state.open(policy, lambda: opened.append(True))
        # Then: the server block is not shortened and no retry occurs
        self.assertEqual([], opened)

    def test_digest_oscillation_requires_selective_purge_without_granting_slots(self) -> None:
        # Given: one digest owns a consumed shared budget
        self.state.reserve(rate_policy())
        # When: a different digest alternates with the authoritative digest
        with self.assertRaises(PolicyDigestMismatchError):
            self.state.reserve(rate_policy(digest=OTHER_DIGEST))
        old_reservation = self.state.reserve(rate_policy())
        self.state.purge(POLICY_ID)
        new_reservation = self.state.reserve(rate_policy(digest=OTHER_DIGEST))
        # Then: only explicit purge changes authority and old cannot oscillate back
        self.assertEqual((30.0, 0.0), (old_reservation.wait_seconds, new_reservation.wait_seconds))
        with self.assertRaises(PolicyDigestMismatchError):
            self.state.reserve(rate_policy())

    def test_digest_oscillation_cannot_erase_retry_after_cooldown(self) -> None:
        # Given: an authoritative digest has a server cooldown
        policy = rate_policy(maximum=20.0)
        self.state.record_retry_after(policy, "90")
        # When: a different digest attempts reservation and cooldown replacement
        with self.assertRaises(PolicyDigestMismatchError):
            self.state.reserve(rate_policy(digest=OTHER_DIGEST))
        with self.assertRaises(PolicyDigestMismatchError):
            self.state.record_retry_after(rate_policy(digest=OTHER_DIGEST), "1")
        # Then: the authoritative digest remains blocked by the original cooldown
        with self.assertRaises(WaitLimitExceededError) as raised:
            self.state.reserve(policy)
        self.assertEqual(90.0, raised.exception.required_seconds)

    def test_robots_ttl_expires_at_exact_boundary(self) -> None:
        # Given: invalid runtime values and a valid decision expiring now
        key = PolicyKey(POLICY_ID, DIGEST)
        invalid = (RobotsEntry(allowed=1, expires_at=100.0), RobotsEntry(True, True), RobotsEntry(True, float("inf")), RobotsEntry(True, 10**400))
        for entry in invalid:
            with self.subTest(entry=entry), self.assertRaises(PolicyConfigurationError):
                self.state.store_robots(key, entry)
        self.state.store_robots(key, RobotsEntry(allowed=False, expires_at=100.0))
        # When: it is read at expires_at
        result = self.state.get_robots(key)
        # Then: expires_at <= now is stale
        self.assertIsNone(result)

    def test_corrupt_locked_and_unwritable_databases_fail_closed(self) -> None:
        # Given: corrupt, locked, and unwritable state paths
        corrupt = Path(self.temporary_directory.name) / "corrupt.sqlite3"
        corrupt.write_bytes(b"not sqlite")
        locked = sqlite3.connect(self.path, isolation_level=None)
        locked.execute("BEGIN IMMEDIATE")
        cases: list[Callable[[], PolicyState]] = [
            lambda: PolicyState(corrupt, clock=self.time.clock, sleeper=self.time.sleep),
            lambda: PolicyState(Path("/dev/null/policy.sqlite3"), clock=self.time.clock, sleeper=self.time.sleep),
        ]
        # When / Then: initialization and a locked write all deny state access
        for factory in cases:
            with self.subTest(factory=factory), self.assertRaises(PolicyStateUnavailableError):
                factory()
        with self.assertRaises(PolicyStateUnavailableError):
            self.state.reserve(rate_policy())
        locked.rollback()
        locked.close()

    def test_clock_is_sampled_after_begin_immediate_acquires_lock(self) -> None:
        # Given: connection setup coordinates a real SQLite lock handoff
        begin_attempted = threading.Event()
        clock_sampled = threading.Event()
        contender = PolicyState(self.path, clock=lambda: (clock_sampled.set(), self.time.now)[1], sleeper=self.time.sleep)
        lock = sqlite3.connect(self.path, isolation_level=None)
        lock.execute("BEGIN IMMEDIATE")
        original_connect = sqlite3.connect

        def traced_connect(path: Path, *, timeout: float, isolation_level: None) -> sqlite3.Connection:
            connection = original_connect(path, timeout=timeout, isolation_level=isolation_level)
            connection.set_trace_callback(lambda sql: begin_attempted.set() if sql == "BEGIN IMMEDIATE" else None)
            return connection

        result: list[float] = []
        worker = threading.Thread(target=lambda: result.append(contender.reserve(rate_policy()).wait_seconds))
        # When: time advances after the real BEGIN attempt but before lock acquisition
        try:
            with patch("kgov_runtime.policy_state.sqlite3.connect", traced_connect):
                worker.start()
                self.assertTrue(begin_attempted.wait(timeout=5.0))
                self.assertFalse(clock_sampled.is_set())
                self.time.now = 130.0
                lock.commit()
                self.assertTrue(clock_sampled.wait(timeout=5.0))
                worker.join(timeout=5.0)
        finally:
            lock.close()
            worker.join(timeout=5.0)
        with closing(sqlite3.connect(self.path)) as connection:
            arrival = connection.execute(
                "SELECT theoretical_arrival FROM rate_state WHERE policy_id = ?", (POLICY_ID,)
            ).fetchone()
        # Then: lock time is excluded and the post-acquisition clock drives GCRA
        self.assertEqual([0.0], result)
        self.assertEqual((160.0,), arrival)

    def test_invalid_numeric_sqlite_state_is_unavailable(self) -> None:
        # Given: SQLite rows with invalid logical REAL values
        for value in ("nonnumeric", float("inf")):
            with self.subTest(value=value):
                self.state.purge()
                self.state.reserve(rate_policy())
                with closing(sqlite3.connect(self.path)) as connection:
                    connection.execute("UPDATE rate_state SET theoretical_arrival = ?", (value,))
                    connection.commit()
                # When / Then: invalid persisted state fails closed uniformly
                with self.assertRaises(PolicyStateUnavailableError):
                    self.state.reserve(rate_policy())

    def test_policy_arithmetic_and_clock_must_remain_finite(self) -> None:
        # Given: finite inputs whose derived interval or tolerance is unrepresentable
        key = PolicyKey(POLICY_ID, DIGEST)
        policies = (RatePolicy(key, True, 60.0, 1, 1.0), RatePolicy(key, 1, True, 1, 1.0), RatePolicy(key, 1, 60.0, True, 1.0), RatePolicy(key, 1, 60.0, 1, True), RatePolicy(key, 10**400, 1.0, 1, 1.0), RatePolicy(key, 10**308, 60.0, 1, 1.0), RatePolicy(key, 1, 1e308, 3, 1e308))
        for policy in policies:
            with self.subTest(policy=policy), self.assertRaises(PolicyConfigurationError):
                self.state.reserve(policy)
        huge_clock = PolicyState(self.path, clock=lambda: 1e308, sleeper=self.time.sleep)
        with self.assertRaises(PolicyConfigurationError):
            huge_clock.reserve(rate_policy())
        unavailable = PolicyState(self.path, clock=lambda: float("inf"), sleeper=self.time.sleep)
        with self.assertRaises(PolicyStateUnavailableError):
            unavailable.reserve(rate_policy())
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual((0,), connection.execute("SELECT count(*) FROM rate_state").fetchone())

    def test_selective_and_all_purge_are_idempotent(self) -> None:
        # Given: state for two policy IDs
        other_id = PolicyId("other-policy")
        self.state.reserve(rate_policy())
        self.state.store_robots(PolicyKey(other_id, DIGEST), RobotsEntry(True, expires_at=200.0))
        # When: one policy then all policies are purged repeatedly
        selective = self.state.purge(POLICY_ID)
        selective_again = self.state.purge(POLICY_ID)
        all_count = self.state.purge()
        all_again = self.state.purge()
        # Then: only rows actually deleted are counted
        self.assertEqual((1, 0, 1, 0), (selective, selective_again, all_count, all_again))

    def test_expiry_purge_uses_less_than_or_equal_boundary(self) -> None:
        # Given: one robots row expiring now and one just after now
        first = PolicyKey(POLICY_ID, DIGEST)
        second = PolicyKey(PolicyId("other-policy"), DIGEST)
        self.state.store_robots(first, RobotsEntry(True, expires_at=100.0))
        self.state.store_robots(second, RobotsEntry(False, expires_at=100.1))
        # When: expired entries are purged
        count = self.state.purge_expired()
        # Then: expires_at <= now is deleted and the later row remains
        self.assertEqual(1, count)
        self.assertIsNone(self.state.get_robots(first))
        self.assertEqual(RobotsEntry(False, 100.1), self.state.get_robots(second))
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("UPDATE robots_state SET expires_at = ?", (float("inf"),))
            connection.commit()
        with self.assertRaises(PolicyStateUnavailableError):
            self.state.purge_expired()

    def test_schema_uses_secure_delete_and_contains_no_content_fields(self) -> None:
        # Given: initialized state and content returned by an opener
        sentinels = " ".join(f"private-{name}" for name in ("url", "query", "body", "record", "credential", "pii"))
        returned = self.state.open(rate_policy(), lambda: sentinels)
        with self.state._connection() as connection:
            # When: storage settings and columns are inspected
            secure_delete = connection.execute("PRAGMA secure_delete").fetchone()
            columns = {row[1] for table in ("rate_state", "robots_state") for row in connection.execute(f"PRAGMA table_info({table})")}
        # Then: deletion is secure and no content-bearing field exists
        self.assertEqual(sentinels, returned)
        self.assertEqual((1,), secure_delete)
        forbidden = {"url", "query", "body", "record", "credential", "pii"}
        self.assertTrue(columns.isdisjoint(forbidden))
        database_bytes = self.path.read_bytes().lower()
        for sentinel in forbidden:
            self.assertNotIn(f"private-{sentinel}".encode(), database_bytes)
