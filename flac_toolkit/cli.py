import logging
import argparse
import sys
from pathlib import Path
from typing import List
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict
from mutagen.flac import FLAC

from flac_toolkit.core import find_flac_files, setup_logging
from flac_toolkit.analyzer import analyze_flac_comprehensive
from flac_toolkit.repair import repair_filename, reencode_flac
from flac_toolkit.replaygain import process_album
from flac_toolkit.reporter import print_analysis_result, print_summary
from flac_toolkit.dataframe import create_dataframe, generate_html_report
from flac_toolkit.dedupe import find_duplicates, print_duplicate_report, generate_dedupe_html_report
from tqdm import tqdm

def analyze(args):
    """
    Perform an in-depth analysis of each file and generate an HTML report.
    """
    logging.info("ANALYZE Mode - In-depth analysis\n" + "=" * 50)
    
    workers = args.workers
    output_html = args.output
    target_paths = [Path(p) for p in args.target_paths]

    files = list(find_flac_files(target_paths))
    if not files:
        logging.warning("No FLAC files found.")
        return

    # Analysis execution
    if workers is not None and workers == 1:
        # Sequential execution (no overhead, smooth progress bar)
        tqdm.write("Running in sequential mode (1 worker).")
        # miniters=1 and mininterval=0.0 force tqdm to update the display after EVERY file
        results = [analyze_flac_comprehensive(f) for f in tqdm(files, unit="file", miniters=1, mininterval=0.0, file=sys.stdout)]
    else:
        # Parallel execution
        import os
        effective_workers = workers if workers else os.cpu_count()
        tqdm.write(f"Running in parallel mode ({effective_workers} workers).")
        with ProcessPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            futures = [executor.submit(analyze_flac_comprehensive, f) for f in files]
            results = []
            # Process results as they complete (fixes progress bar jumps caused by slow files blocking the queue in map)
            for future in tqdm(as_completed(futures), total=len(files), unit="file", miniters=1, mininterval=0.0, file=sys.stdout):
                results.append(future.result())
    
    # Console Output
    for r in results:
        print_analysis_result(r)
    print_summary(results)

    # Generate HTML Report
    logging.info("\nGenerating HTML report...")
    df = create_dataframe(results)
    generate_html_report(df, output_html)


def repair_worker(file_path: Path, force: bool):
    if force:
        reencode_flac(file_path)
        return

    analysis = analyze_flac_comprehensive(file_path)
    if not analysis['repair_suggestions']:
        logging.debug(f"OK: {file_path.name}")
        return
    
    logging.info(f"Issues found in: {file_path.name}")
    for suggestion in analysis['repair_suggestions']:
        if suggestion['action'] == 'reencode':
            reencode_flac(file_path)
        elif suggestion['action'] == 'rename':
            repair_filename(file_path)


def repair(args):
    """
    Repair files based on analysis. Use --force to re-encode all.
    """
    force = args.force
    workers = args.workers
    target_paths = [Path(p) for p in args.target_paths]
    
    if force:
        logging.info("REPAIR Mode (Forced) - Re-encoding all files\n" + "=" * 50)
    else:
        logging.info("REPAIR Mode (Auto) - Analyzing and repairing problematic files\n" + "=" * 50)

    files = list(find_flac_files(target_paths))
    if not files:
        logging.warning("No FLAC files found.")
        return

    # Limit workers to ProcessPoolExecutor's maximum (61 on Windows)
    if workers is not None and workers > 61:
        logging.warning(f"Requested {workers} workers exceeds system limit. Capping at 61.")
        workers = 61

    if workers is not None and workers == 1:
        tqdm.write("Running in sequential mode (1 worker).")
        for f in tqdm(files, unit="file", miniters=1, mininterval=0.0, file=sys.stdout):
            repair_worker(f, force)
    else:
        import os
        effective_workers = workers if workers else os.cpu_count()
        tqdm.write(f"Running in parallel mode ({effective_workers} workers).")
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(repair_worker, f, force) for f in files]
            for future in tqdm(as_completed(futures), total=len(files), unit="file", miniters=1, mininterval=0.0, file=sys.stdout):
                future.result()

    logging.info("\nRepair process completed.")

def replaygain(args):
    """
    Calculate and apply ReplayGain tags.
    """
    assume_album = args.assume_album
    target_paths = [Path(p) for p in args.target_paths]
    
    logging.info("REPLAYGAIN Mode - Calculate and apply track/album ReplayGain\n" + "=" * 50)

    files = list(find_flac_files(target_paths))
    if not files:
        logging.warning("No FLAC files found.")
        return

    albums = defaultdict(list)
    if assume_album:
        logging.info("Assuming all provided files belong to a single album.")
        albums["<Assumed Album>"] = files
    else:
        logging.info("Grouping files by album metadata...")
        for file_path in files:
            try:
                audio = FLAC(file_path)
                album_tag = (audio["album"][0] if "album" in audio else "_NO_ALBUM_TAG_")
                albums[album_tag].append(file_path)
            except Exception as e:
                logging.warning(f"Could not read metadata from {file_path.name}: {e}")

    
    album_items = list(albums.items())

    for album_name, album_files in album_items:
        logging.info(f"\n--- Processing Album: {album_name} ({len(album_files)} tracks) ---")
        process_album(album_files)

def dedupe(args):
    """
    Find duplicate FLAC files.
    """
    logging.info("DEDUPE Mode - Scanning for duplicates\n" + "=" * 50)
    target_paths = [Path(p) for p in args.target_paths]
    output_html = args.output
    
    results = find_duplicates(target_paths)
    print_duplicate_report(results)
    
    # Generate HTML Report
    if results:
        logging.info("\nGenerating HTML report...")
        generate_dedupe_html_report(results, Path(output_html))

def main():
    parser = argparse.ArgumentParser(
        prog='flac_toolkit',
        description='FLAC Toolkit - Advanced diagnosis, repair, and ReplayGain tool.'
    )
    
    # Global options
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose (debug) output.')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress all output except errors.')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Perform an in-depth analysis of each file and generate an HTML report.')
    analyze_parser.add_argument('target_paths', nargs='+', help='One or more files or directories to process.')
    analyze_parser.add_argument('-w', '--workers', type=int, default=None, help='Number of parallel workers.')
    analyze_parser.add_argument('-o', '--output', type=str, default='flac_analysis_report.html', help='Path to the output HTML report.')
    
    # Repair command
    repair_parser = subparsers.add_parser('repair', help='Repair files based on analysis. Use --force to re-encode all.')
    repair_parser.add_argument('target_paths', nargs='+', help='One or more files or directories to process.')
    repair_parser.add_argument('--force', action='store_true', help='Force re-encoding on all files.')
    repair_parser.add_argument('-w', '--workers', type=int, default=None, help='Number of parallel workers.')
    
    # ReplayGain command
    replaygain_parser = subparsers.add_parser('replaygain', help='Calculate and apply ReplayGain tags.')
    replaygain_parser.add_argument('target_paths', nargs='+', help='One or more files or directories to process.')
    replaygain_parser.add_argument('--assume-album', action='store_true', help='Treat all files as one album.')
    
    # Dedupe command
    dedupe_parser = subparsers.add_parser('dedupe', help='Find duplicate FLAC files (strict and audio-only).')
    dedupe_parser.add_argument('target_paths', nargs='+', help='One or more files or directories to process.')
    dedupe_parser.add_argument('-o', '--output', type=str, default='flac_duplicate_report.html', help='Path to the output HTML report.')
    
    args = parser.parse_args()
    
    # Setup logging based on global flags
    setup_logging(args.verbose, args.quiet)
    
    # Dispatch to the appropriate command
    if args.command == 'analyze':
        analyze(args)
    elif args.command == 'dedupe':
        dedupe(args)
    elif args.command == 'repair':
        repair(args)
    elif args.command == 'replaygain':
        replaygain(args)


if __name__ == "__main__":
    main()
