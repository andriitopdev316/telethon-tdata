"""CLI: convert sessions/ → tdatas/."""

import logging
import sys

import converter as conv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> int:
    conv.ensure_dirs()
    names = conv.discover_session_names()
    if not names:
        logging.error("No session folders found in ./sessions")
        return 1

    def log(msg: str) -> None:
        logging.info(msg)

    ok, failed = conv.run_async(conv.convert_sessions(names, log=log))
    logging.info("Done. Success: %s, failed: %s", len(ok), len(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
