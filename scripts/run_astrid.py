from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--workspace", default=None)
    args, passthrough = parser.parse_known_args(argv)

    if args.workspace:
        os.chdir(args.workspace)

    from astrid.main import main as astrid_main

    sys.argv = ["astrid", *passthrough]
    astrid_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
