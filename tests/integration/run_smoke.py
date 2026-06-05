import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.integration.smoke_test import run_smoke_test

def setup_logging():
    """Configure logging to console and file with timestamps."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"smoke_test_{timestamp}.log"

    logger = logging.getLogger("smoke_runner")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(ch)

    return logger, log_file

def main():
    logger, log_file = setup_logging()
    logger.info("=== Smoke Test Runner Started ===")
    logger.info(f"Log file: {log_file}")

    try:
        logger.info("Starting smoke test execution...")
        result = run_smoke_test()
        if result:
            logger.info("Smoke test completed successfully.")
            logger.info("=== Smoke Test Runner Finished (SUCCESS) ===")
            return 0
        else:
            logger.error("Smoke test failed.")
            logger.info("=== Smoke Test Runner Finished (FAILURE) ===")
            return 1
    except Exception as e:
        logger.exception(f"Smoke test raised an exception: {e}")
        logger.info("=== Smoke Test Runner Finished (ERROR) ===")
        return 1

if __name__ == "__main__":
    sys.exit(main())