import os
import sys
import logging
import platform
from pathlib import Path
from typing import Iterator, List, Callable, Any
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, as_completed
from flac_toolkit.constants import QUARANTINE_FOLDER_NAME
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, MofNCompleteColumn
from rich.console import Console

def setup_logging(verbose: bool = False, quiet: bool = False):
    """Configure logging for the application."""
    log_level = logging.INFO
    if verbose:
        log_level = logging.DEBUG
    if quiet:
        log_level = logging.ERROR
    
    # Simple format for INFO, detailed for DEBUG
    log_format = '%(message)s' if log_level > logging.DEBUG else '%(levelname)s: %(message)s'
    
    # Force reconfiguration of the root logger to ensure our settings are applied
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Use RichHandler for beautiful logging that doesn't break progress bars
    rich_handler = RichHandler(
        level=log_level,
        console=Console(stderr=True),
        show_time=False,
        show_path=False,
        markup=True,
        rich_tracebacks=True
    )
    rich_handler.setFormatter(logging.Formatter(log_format))
    root.addHandler(rich_handler)
    root.setLevel(log_level)


def _cap_workers(workers: int | None) -> int | None:
    """Cap workers to 61 on Windows (ProcessPoolExecutor limitation)."""
    if platform.system() == 'Windows' and workers is not None and workers > 61:
        logging.warning(f"Requested {workers} workers exceeds Windows limit. Capping at 61.")
        return 61
    return workers


@contextmanager
def flac_progress(description: str):
    """Reusable Rich progress bar context manager."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        expand=True
    ) as progress:
        yield progress, description


def run_parallel(
    files: List[Path],
    worker_fn: Callable[..., Any],
    workers: int | None,
    description: str,
    worker_args: tuple = (),
    collect_results: bool = True,
) -> List[Any]:
    """Run worker_fn over files with a unified progress bar.

    Parameters
    ----------
    files : list of paths
    worker_fn : callable(file_path, *worker_args) -> result
    workers : number of workers (None = cpu_count, 1 = sequential)
    description : progress bar label
    worker_args : extra positional args passed after file_path
    collect_results : if False, results of futures are discarded (repair mode)
    """
    workers = _cap_workers(workers)
    results: List[Any] = []

    with flac_progress(description) as (progress, _desc):
        if workers is not None and workers == 1:
            logging.info("Running in [bold]sequential[/bold] mode (1 worker).")
            task = progress.add_task(description, total=len(files))
            for f in files:
                res = worker_fn(f, *worker_args)
                if collect_results:
                    results.append(res)
                progress.advance(task)
        else:
            effective_workers = workers if workers else os.cpu_count()
            logging.info(f"Running in [bold]parallel[/bold] mode ({effective_workers} workers).")
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(worker_fn, f, *worker_args) for f in files]
                task = progress.add_task(description, total=len(files))
                for future in as_completed(futures):
                    res = future.result()
                    if collect_results:
                        results.append(res)
                    progress.advance(task)

    return results

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
