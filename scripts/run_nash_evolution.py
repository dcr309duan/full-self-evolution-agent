import os
import sys
import logging
import time
from datetime import datetime

# Add parent directory to path to allow imports from core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evolution_orchestrator import EvolutionOrchestrator

def setup_logging(timestamp: str) -> str:
    """Configure logging to both console and a timestamped file."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"nash_evolution_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return log_file

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = setup_logging(timestamp)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("Nash Evolution Runner Started")
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 60)
    
    # Configurable parameters
    max_cycles = 100
    module_list = [
        "core.nash_detector_and_forcer",
        "core.test_suite_evolver",
        "core.evolution_orchestrator"
    ]
    
    logger.info(f"Configuration:")
    logger.info(f"  Max cycles: {max_cycles}")
    logger.info(f"  Module list: {module_list}")
    
    orchestrator = EvolutionOrchestrator()
    
    try:
        logger.info("Starting evolution loop...")
        start_time = time.time()
        
        orchestrator.run_evolution(
            max_cycles=max_cycles,
            module_list=module_list
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Evolution completed successfully in {elapsed:.2f} seconds")
        
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Initiating graceful shutdown...")
        orchestrator.shutdown()
        elapsed = time.time() - start_time
        logger.info(f"Evolution interrupted after {elapsed:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Evolution failed with error: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("Nash Evolution Runner Finished")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()