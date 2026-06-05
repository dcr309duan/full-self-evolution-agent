#!/usr/bin/env python3
"""
scripts/build_self_model.py

Standalone script that imports SelfModelBuilder, runs it on the current codebase,
and saves the resulting graph. This can be invoked by the scheduler or orchestrator.
"""

import sys
import os
import argparse
import logging

# Add the project root to sys.path if needed (assumes script is in 'scripts/' directory)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from self_model.builder import SelfModelBuilder

def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the self-model graph from the current codebase."
    )
    parser.add_argument(
        "--codebase-path",
        type=str,
        default=project_root,
        help="Path to the codebase root directory (default: project root)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(project_root, "self_model_graph.json"),
        help="Output file path for the saved graph (default: self_model_graph.json in project root)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose debug logging"
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("build_self_model")

    # Validate codebase path
    codebase_path = os.path.abspath(args.codebase_path)
    if not os.path.isdir(codebase_path):
        logger.error(f"Codebase path does not exist or is not a directory: {codebase_path}")
        sys.exit(1)

    logger.info(f"Starting self-model build for codebase: {codebase_path}")
    logger.info(f"Output graph will be saved to: {args.output}")

    try:
        builder = SelfModelBuilder(codebase_path=codebase_path)
        graph = builder.build()
        builder.save_graph(graph, args.output)
        logger.info("Self-model graph built and saved successfully.")
    except Exception as e:
        logger.exception(f"Failed to build self-model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()