import sys
import logging
from pathlib import Path
from typing import Iterator, List
from flac_toolkit.constants import QUARANTINE_FOLDER_NAME

def setup_logging(verbose: bool = False, quiet: bool = False):
    """Configure logging for the application."""
    log_level = logging.INFO
    if verbose:
        log_level = logging.DEBUG
    if quiet:
        log_level = logging.ERROR
    
    # Simple format for INFO, detailed for DEBUG
    log_format = '%(message)s' if log_level > logging.DEBUG else '%(levelname)s: %(message)s'
    
    # Basic configuration
    logging.basicConfig(level=log_level, format=log_format, stream=sys.stdout)

def find_flac_files(target_paths: List[Path]) -> Iterator[Path]:
    """Recursively search for FLAC files in given paths."""
    for path in target_paths:
        if not path.exists():
            logging.warning(f"Path '{path}' does not exist.")
            continue
        if path.is_file() and path.suffix.lower() == '.flac':
            yield path
        elif path.is_dir():
            for p in path.rglob('*.flac'):
                if QUARANTINE_FOLDER_NAME not in p.parts:
                    yield p
