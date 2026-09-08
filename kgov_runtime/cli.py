"""Non-reflecting argparse errors for public runtime CLIs."""

import argparse
from typing import NoReturn


class SafeArgumentParser(argparse.ArgumentParser):
    """Keep argument validation and help without echoing rejected input."""

    def error(self, _message: str) -> NoReturn:
        self.exit(2, "ERROR invalid command-line arguments\n")
