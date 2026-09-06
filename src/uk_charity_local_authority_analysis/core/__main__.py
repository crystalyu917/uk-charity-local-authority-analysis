"""Build the integrated charity register."""

import logging

from uk_charity_local_authority_analysis.core import (
    build_charity_register,
)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(build_charity_register())
