"""Process-shared SQLite state for source access policies."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import timedelta
from email.utils import format_datetime, parsedate_to_datetime
from math import isfinite
from pathlib import Path
from typing import Final, NewType, TypeVar

PolicyId = NewType("PolicyId", str)
PolicyDigest = NewType("PolicyDigest", str)
_BUSY_TIMEOUT_SECONDS: Final = 0.25


@dataclass(frozen=True, slots=True)
class PolicyKey:
    """Stable policy identity supplied by the policy parser boundary."""

    policy_id: PolicyId
    digest: PolicyDigest


@dataclass(frozen=True, slots=True)
class RatePolicy:
    """Reviewed GCRA budget and its maximum caller wait."""

    key: PolicyKey
    requests: int
    per_seconds: float
    burst: int
    max_wait_seconds: float


@dataclass(frozen=True, slots=True)
class Reservation:
    wait_seconds: float


@dataclass(frozen=True, slots=True)
class RobotsEntry:
    allowed: bool
    expires_at: float


class WaitLimitExceededError(RuntimeError):
    def __init__(self, required_seconds: float, maximum_seconds: float) -> None:
        self.required_seconds = required_seconds
        self.maximum_seconds = maximum_seconds

    def __str__(self) -> str:
        return f"required wait {self.required_seconds:g}s exceeds cap {self.maximum_seconds:g}s"


class RetryAfterError(RuntimeError):
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return "Retry-After is malformed"


class PolicyDigestMismatchError(RuntimeError):
    def __init__(self, policy_id: PolicyId) -> None:
        self.policy_id = policy_id

    def __str__(self) -> str:
        return f"policy digest conflicts with persisted state: {self.policy_id}"


class PolicyConfigurationError(RuntimeError):
    def __init__(self, policy_id: PolicyId) -> None:
        self.policy_id = policy_id

    def __str__(self) -> str:
        return f"invalid rate policy: {self.policy_id}"


class PolicyStateUnavailableError(RuntimeError):
    def __init__(self, path: Path) -> None:
        self.path = path

    def __str__(self) -> str:
        return f"policy state is unavailable: {self.path}"


Result = TypeVar("Result")


def policy_state_path() -> Path:
    if configured := os.environ.get("KGOV_POLICY_STATE_PATH"):
        return Path(configured)
    if xdg_state := os.environ.get("XDG_STATE_HOME"):
        return Path(xdg_state) / "k-gov-skills/policy-state.sqlite3"
    return Path.home() / ".local/state/k-gov-skills/policy-state.sqlite3"


class PolicyState:
    """Own metadata-only policy state at a caller-selected SQLite path."""

    def __init__(self, path: Path, *, clock: Callable[[], float], sleeper: Callable[[float], None]) -> None:
        self._path = path
        self._clock = clock
        self._sleeper = sleeper
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE IF NOT EXISTS rate_state (policy_id TEXT PRIMARY KEY, policy_digest TEXT NOT NULL, theoretical_arrival REAL NOT NULL, blocked_until REAL NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS robots_state (policy_id TEXT PRIMARY KEY, policy_digest TEXT NOT NULL, allowed INTEGER NOT NULL CHECK (allowed IN (0, 1)), expires_at REAL NOT NULL)")
            connection.commit()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        try:
            database = sqlite3.connect(self._path, timeout=_BUSY_TIMEOUT_SECONDS, isolation_level=None)
            with closing(database) as connection:
                connection.execute("PRAGMA secure_delete=ON")
                yield connection
        except sqlite3.Error as error:
            raise PolicyStateUnavailableError(self._path) from error

    @staticmethod
    def _require_digest(connection: sqlite3.Connection, key: PolicyKey) -> None:
        for table in ("rate_state", "robots_state"):
            statement = f"SELECT policy_digest FROM {table} WHERE policy_id = ?"
            row = connection.execute(statement, (key.policy_id,)).fetchone()
            if row is not None and row[0] != key.digest:
                raise PolicyDigestMismatchError(key.policy_id)

    @staticmethod
    def _number(value: int | float | str | bytes | None) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise sqlite3.DataError from error
        if not isfinite(number):
            raise sqlite3.DataError
        return number

    @staticmethod
    def _configuration_number(value: int | float, policy_id: PolicyId) -> float:
        try:
            return PolicyState._number(value)
        except sqlite3.DataError as error:
            raise PolicyConfigurationError(policy_id) from error

    def reserve(self, policy: RatePolicy) -> Reservation:
        """Atomically reserve one GCRA slot, then perform the bounded wait."""
        values = (policy.requests, policy.per_seconds, policy.burst, policy.max_wait_seconds)
        if type(policy.requests) is not int or type(policy.burst) is not int or any(type(value) not in (int, float) for value in values):
            raise PolicyConfigurationError(policy.key.policy_id)
        requests, period, burst, maximum = (self._configuration_number(value, policy.key.policy_id) for value in values)
        if requests <= 0 or period <= 0 or burst <= 0 or maximum < 0:
            raise PolicyConfigurationError(policy.key.policy_id)
        interval = period / requests
        tolerance = interval * (burst - 1)
        if interval <= 0 or not isfinite(interval) or not isfinite(tolerance):
            raise PolicyConfigurationError(policy.key.policy_id)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = self._number(self._clock())
            self._require_digest(connection, policy.key)
            row = connection.execute(
                "SELECT theoretical_arrival, blocked_until FROM rate_state WHERE policy_id = ?", (policy.key.policy_id,)
            ).fetchone()
            if row is None:
                theoretical_arrival = now
                blocked_until = now
            else:
                theoretical_arrival = self._number(row[0])
                blocked_until = self._number(row[1])
            eligible_at = self._number(theoretical_arrival - tolerance)
            allowed_at = self._number(max(now, eligible_at, blocked_until))
            wait_seconds = self._number(allowed_at - now)
            if wait_seconds > maximum:
                raise WaitLimitExceededError(wait_seconds, maximum)
            arrival_base = max(theoretical_arrival, allowed_at)
            next_arrival = arrival_base + interval
            if not isfinite(next_arrival) or next_arrival <= arrival_base:
                raise PolicyConfigurationError(policy.key.policy_id)
            connection.execute(
                "INSERT INTO rate_state VALUES (?, ?, ?, ?) ON CONFLICT(policy_id) DO UPDATE SET "
                "policy_digest=excluded.policy_digest, theoretical_arrival=excluded.theoretical_arrival, "
                "blocked_until=excluded.blocked_until",
                (policy.key.policy_id, policy.key.digest, next_arrival, blocked_until),
            )
            connection.commit()
        if wait_seconds > 0:
            self._sleeper(wait_seconds)
        return Reservation(wait_seconds)

    def open(self, policy: RatePolicy, opener: Callable[[], Result]) -> Result:
        """Reserve once and recheck shared cooldown/digest after each bounded wait."""
        waited = self.reserve(policy).wait_seconds
        while True:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                now = self._number(self._clock())
                self._require_digest(connection, policy.key)
                row = connection.execute(
                    "SELECT blocked_until FROM rate_state WHERE policy_id = ?", (policy.key.policy_id,)
                ).fetchone()
                wait = self._number(max(0.0, self._number(row[0]) - now)) if row else 0.0
                if wait > 0:
                    required = self._number(waited + wait)
                    if required > policy.max_wait_seconds:
                        raise WaitLimitExceededError(required, policy.max_wait_seconds)
                    if required <= waited:
                        raise sqlite3.DataError
                    waited = required
                connection.commit()
            if wait <= 0:
                break
            self._sleeper(wait)
        return opener()

    def record_retry_after(self, policy: RatePolicy, value: str) -> float:
        """Persist a 429 Retry-After delta or HTTP-date without retrying."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = self._number(self._clock())
            self._require_digest(connection, policy.key)
            stripped = value.strip()
            try:
                if stripped.isascii() and stripped.isdigit():
                    delay = float(stripped)
                else:
                    parsed = parsedate_to_datetime(stripped)
                    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
                        raise RetryAfterError(value)
                    if format_datetime(parsed, usegmt=True) != stripped:
                        raise RetryAfterError(value)
                    delay = max(0.0, parsed.timestamp() - now)
                if not isfinite(delay):
                    raise RetryAfterError(value)
            except (TypeError, ValueError, OverflowError) as error:
                raise RetryAfterError(value) from error
            blocked_until = now + delay
            if not isfinite(blocked_until):
                raise RetryAfterError(value)
            row = connection.execute(
                "SELECT theoretical_arrival, blocked_until FROM rate_state WHERE policy_id = ?", (policy.key.policy_id,)
            ).fetchone()
            theoretical_arrival = now
            if row is not None:
                theoretical_arrival = self._number(row[0])
                blocked_until = max(blocked_until, self._number(row[1]))
            connection.execute(
                "INSERT INTO rate_state VALUES (?, ?, ?, ?) ON CONFLICT(policy_id) DO UPDATE SET "
                "policy_digest=excluded.policy_digest, theoretical_arrival=excluded.theoretical_arrival, "
                "blocked_until=excluded.blocked_until",
                (policy.key.policy_id, policy.key.digest, theoretical_arrival, blocked_until),
            )
            connection.commit()
        return delay

    def store_robots(self, key: PolicyKey, entry: RobotsEntry) -> None:
        """Store only a robots decision, policy digest, and expiry."""
        valid_expiry = type(entry.expires_at) in (int, float)
        if type(entry.allowed) is not bool or not valid_expiry:
            raise PolicyConfigurationError(key.policy_id)
        expires_at = self._configuration_number(entry.expires_at, key.policy_id)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_digest(connection, key)
            connection.execute(
                "INSERT INTO robots_state VALUES (?, ?, ?, ?) ON CONFLICT(policy_id) DO UPDATE SET "
                "policy_digest=excluded.policy_digest, allowed=excluded.allowed, expires_at=excluded.expires_at",
                (key.policy_id, key.digest, entry.allowed, expires_at),
            )
            connection.commit()

    def get_robots(self, key: PolicyKey) -> RobotsEntry | None:
        """Return a current same-digest decision, deleting stale state."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = self._number(self._clock())
            self._require_digest(connection, key)
            row = connection.execute(
                "SELECT policy_digest, allowed, expires_at FROM robots_state WHERE policy_id = ?", (key.policy_id,)
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            if self._number(row[2]) <= now:
                connection.execute("DELETE FROM robots_state WHERE policy_id = ?", (key.policy_id,))
                connection.commit()
                return None
            connection.commit()
            allowed = self._number(row[1])
            if allowed not in (0.0, 1.0):
                raise sqlite3.DataError
            return RobotsEntry(allowed=bool(allowed), expires_at=self._number(row[2]))

    def purge(self, policy_id: PolicyId | None = None) -> int:
        """Delete one policy's state, or all state, idempotently."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if policy_id is None:
                rate = connection.execute("DELETE FROM rate_state").rowcount
                robots = connection.execute("DELETE FROM robots_state").rowcount
            else:
                rate = connection.execute("DELETE FROM rate_state WHERE policy_id = ?", (policy_id,)).rowcount
                robots = connection.execute("DELETE FROM robots_state WHERE policy_id = ?", (policy_id,)).rowcount
            connection.commit()
        return rate + robots

    def purge_expired(self) -> int:
        """Delete robots entries whose typed expiry is at or before now."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = self._number(self._clock())
            rows = connection.execute("SELECT policy_id, expires_at FROM robots_state").fetchall()
            expired = [(row[0],) for row in rows if self._number(row[1]) <= now]
            connection.executemany("DELETE FROM robots_state WHERE policy_id = ?", expired)
            connection.commit()
        return len(expired)
