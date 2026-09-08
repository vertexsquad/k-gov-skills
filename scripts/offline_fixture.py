"""Run a fixture module with CPython socket audit events denied.

This guards Python fixture code, not native code or descendant processes.
"""

from __future__ import annotations

import argparse
import runpy
import sys


def deny_network(event: str, _args: tuple[object, ...]) -> None:
    if event.startswith("socket."):
        raise RuntimeError(f"offline-fixture-network-disabled: {event}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", help="fixture module to execute as __main__")
    parser.add_argument("argv", nargs=argparse.REMAINDER, help="arguments passed to the fixture")
    # Parse only the runner's module; even a leading -- belongs to the target.
    args = parser.parse_args(sys.argv[1:2])
    sys.argv = [args.module, *sys.argv[2:]]
    sys.addaudithook(deny_network)
    runpy.run_module(args.module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
