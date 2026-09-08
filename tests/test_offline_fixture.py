"""Real child-process regressions for the offline fixture boundary."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import render_domain_skills

ROOT = Path(__file__).resolve().parents[1]


class OfflineFixtureTest(unittest.TestCase):
    def test_renderer_blocks_dns_before_target_package_import(self) -> None:
        # Numeric-only resolution is safe even when the guard is missing.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "network_probe"
            package.mkdir()
            (package / "__init__.py").write_text(
                "import socket\n"
                "socket.getaddrinfo('127.0.0.1', 0, flags=socket.AI_NUMERICHOST)\n",
                encoding="utf-8",
            )
            (package / "__main__.py").write_text("print('probe-completed')\n", encoding="utf-8")
            with (
                patch.object(render_domain_skills, "ROOT", root),
                patch.dict(os.environ, {"PYTHONPATH": str(ROOT)}),
            ):
                control = subprocess.run(
                    [sys.executable, "-m", "network_probe"],
                    cwd=root, capture_output=True, check=False, timeout=10,
                )
                self.assertEqual(0, control.returncode, control.stderr)
                self.assertEqual(b"probe-completed\n", control.stdout)
                render_domain_skills.fixture_receipt.cache_clear()
                self.addCleanup(render_domain_skills.fixture_receipt.cache_clear)
                receipt = render_domain_skills.fixture_receipt("network_probe", ())
            self.assertNotEqual(0, receipt.returncode, receipt.stdout)
            self.assertEqual(b"", receipt.stdout)
            self.assertIn(b"offline-fixture-network-disabled: socket.getaddrinfo", receipt.stderr)

    def test_renderer_blocks_socket_creation_in_the_child(self) -> None:
        # Given a safe socket-allocation control with no connect or bind.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "socket_probe.py").write_text(
                "import socket\nwith socket.socket():\n    print('socket-created')\n",
                encoding="utf-8",
            )
            with (
                patch.object(render_domain_skills, "ROOT", root),
                patch.dict(os.environ, {"PYTHONPATH": str(ROOT)}),
            ):
                control = subprocess.run(
                    [sys.executable, "-m", "socket_probe"],
                    cwd=root, capture_output=True, check=False, timeout=10,
                )
                self.assertEqual(0, control.returncode, control.stderr)
                self.assertEqual(b"socket-created\n", control.stdout)
                render_domain_skills.fixture_receipt.cache_clear()
                self.addCleanup(render_domain_skills.fixture_receipt.cache_clear)
                # When the real renderer launches the same target.
                receipt = render_domain_skills.fixture_receipt("socket_probe", ())
            # Then allocation fails before the target obtains a socket.
            self.assertNotEqual(0, receipt.returncode, receipt.stdout)
            self.assertEqual(b"", receipt.stdout)
            self.assertIn(b"offline-fixture-network-disabled: socket.__new__", receipt.stderr)

    def test_runner_preserves_module_argv_streams_and_exit_status(self) -> None:
        # Given a target with a relative import and nonzero exit status.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "argv_probe"
            package.mkdir()
            (package / "__init__.py").write_text("STATUS = 7\n", encoding="utf-8")
            (package / "__main__.py").write_text(
                "import json, sys\nfrom . import STATUS\n"
                "print(json.dumps([sys.argv, __name__, __package__]))\n"
                "sys.stderr.buffer.write(b'probe-stderr\\n')\n"
                "raise SystemExit(STATUS)\n",
                encoding="utf-8",
            )
            argv = ["--", "--help", "--fixture=value", "two words", "", "--", "-x"]
            environment = os.environ | {"PYTHONPATH": str(ROOT)}
            direct = subprocess.run(
                [sys.executable, "-m", "argv_probe", *argv],
                cwd=root, env=environment, capture_output=True, check=False, timeout=10,
            )
            self.assertEqual(7, direct.returncode, direct.stderr)
            # When the runner executes that same module and argv.
            guarded = subprocess.run(
                [sys.executable, "-m", "scripts.offline_fixture", "argv_probe", *argv],
                cwd=root, env=environment, capture_output=True, check=False, timeout=10,
            )
            # Then runpy retains -m identity, argv[0], output bytes and status.
            self.assertEqual(
                (direct.returncode, direct.stdout, direct.stderr),
                (guarded.returncode, guarded.stdout, guarded.stderr),
            )

    def test_real_capability_receipts_are_unchanged(self) -> None:
        # Given success, help and input-error paths through the real parsers.
        for module, argv in (
            ("kgov_runtime.capabilities.public_document_hwpx", ("--fixture",)),
            ("kgov_runtime.capabilities.kosis_official_statistics", ("--fixture",)),
            ("kgov_runtime.capabilities.public_document_hwpx", ("--help",)),
            ("kgov_runtime.capabilities.public_document_hwpx", ("--invalid",)),
        ):
            with self.subTest(module=module, argv=argv):
                direct = subprocess.run(
                    [sys.executable, "-m", module, *argv],
                    cwd=ROOT, capture_output=True, check=False, timeout=10,
                    env=os.environ | {"PYTHONIOENCODING": "utf-8"},
                )
                # When the renderer uses the guarded child.
                guarded = render_domain_skills.fixture_receipt(module, argv)
                # Then original fixture/CLI output bytes and exits survive.
                self.assertEqual(
                    (direct.returncode, direct.stdout, direct.stderr),
                    (guarded.returncode, guarded.stdout, guarded.stderr),
                )


if __name__ == "__main__":
    unittest.main()
