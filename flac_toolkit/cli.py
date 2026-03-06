"""
flac_toolkit/cli.py
Command-line interface for FLAC Toolkit with RFC 9639 validation.
"""

import logging
import argparse
import sys


def validate(args):
    """
    Validate FLAC files against RFC 9639 specification and generate HTML report.
    """
    from pathlib import Path
    from collections import defaultdict
    from flac_toolkit.core import find_flac_files, run_parallel
    from flac_toolkit.analyzer import analyze_flac_comprehensive
    from flac_toolkit.dataframe import create_dataframe, generate_html_report

    logging.info("[bold cyan]VALIDATE Mode[/bold cyan] - [white]RFC 9639 Compliance Check[/white]\n" + "=" * 50)

    target_paths = [Path(p) for p in args.target_paths]

    output_html = args.output
    if output_html == 'flac_validation_report.html':  # default sentinal → derive from target
        first_target = target_paths[0]
        target_name = first_target.stem if first_target.is_file() else (first_target.name or first_target.parent.name)
        safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in target_name)
        output_html = f'flac_validation_report_{safe_name}.html'

    files = list(find_flac_files(target_paths))
    if not files:
        logging.warning("No FLAC files found.")
        return

    results = run_parallel(files, analyze_flac_comprehensive, args.workers, "Validating files...")

    # Print console summary
    total = len(results)
    valid_count = sum(1 for r in results if r['status'] == 'VALID')
    warn_count = sum(1 for r in results if r['status'] == 'VALID (with warnings)')
    invalid_count = total - valid_count - warn_count
    logging.info(f"\n{'='*70}\nFINAL SUMMARY\n{'='*70}")
    logging.info(f"Total files scanned: {total}")
    logging.info(f"✓ Valid files: {valid_count}")
    logging.info(f"✓ Valid files (with warnings): {warn_count}")
    logging.info(f"✗ Invalid files: {invalid_count}")
    logging.info(f"{'='*70}")

    # Duplicate detection: MD5s already computed during validation — no extra I/O.
    duplicate_groups = None
    if args.check_duplicates:
        logging.info("\n[bold cyan]Checking for duplicates...[/bold cyan]")
        from flac_toolkit.dedupe import build_duplicate_groups

        audio_md5_map: dict = defaultdict(list)
        for r in results:
            md5 = (r.get('metrics') or {}).get('md5_calculated')
            if md5:
                audio_md5_map[md5].append(Path(r['file']))

        duplicate_groups = build_duplicate_groups(audio_md5_map)

        if duplicate_groups:
            total_dup_files = sum(len(g.files) for g in duplicate_groups)
            strict_sets = sum(len(g.strict_groups) for g in duplicate_groups)
            logging.info(
                f"Found [bold]{len(duplicate_groups)}[/bold] duplicate groups "
                f"({total_dup_files} files, {strict_sets} strict sets)."
            )
        else:
            logging.info("No audio duplicates found.")

    logging.info("\nGenerating HTML report...")
    df = create_dataframe(results)
    generate_html_report(df, Path(output_html), duplicate_groups=duplicate_groups)

    # Save machine-readable JSON alongside the HTML for later re-generation
    from flac_toolkit.dataframe import save_report_data
    json_path = Path(output_html).with_suffix('.json')
    save_report_data(results, json_path, duplicate_groups=duplicate_groups)



def repair(args):
    """
    Repair files based on validation. Use --force to re-encode all.
    """
    from pathlib import Path
    from flac_toolkit.core import find_flac_files, run_parallel
    from flac_toolkit.repair import repair_worker

    force = args.force
    no_backup = args.no_backup
    workers = args.workers
    target_paths = [Path(p) for p in args.target_paths]

    if force:
        logging.info("[bold yellow]REPAIR Mode (Forced)[/bold yellow] - [white]Re-encoding all files[/white]\n" + "=" * 50)
    else:
        logging.info("[bold cyan]REPAIR Mode (Auto)[/bold cyan] - [white]Validating and repairing problematic files[/white]\n" + "=" * 50)

    if no_backup:
        logging.info("[bold red]No-backup mode enabled[/bold red]: original files will be [bold underline]deleted[/bold underline] after successful repair.")

    # Detect and display which encoder will be used
    import shutil
    if shutil.which('flac'):
        logging.info("Encoder: [bold]flac[/bold] (compression level 8 --best)")
    elif shutil.which('ffmpeg'):
        logging.info("Encoder: [bold]ffmpeg[/bold] (compression level 12)")
    else:
        logging.warning("No encoder found (flac or ffmpeg required)")

    files = list(find_flac_files(target_paths))
    if not files:
        logging.warning("No FLAC files found.")
        return

    run_parallel(
        files, repair_worker, workers, "Repairing files...",
        worker_args=(force, no_backup), collect_results=False
    )

    logging.info("\nRepair process completed.")


def replaygain(args):
    """
    Calculate and apply ReplayGain tags.
    """
    from pathlib import Path
    from collections import defaultdict
    from mutagen.flac import FLAC
    from flac_toolkit.core import find_flac_files
    from flac_toolkit.replaygain import process_album

    assume_album = args.assume_album
    target_paths = [Path(p) for p in args.target_paths]

    logging.info("[bold magenta]REPLAYGAIN Mode[/bold magenta] - [white]Calculate and apply track/album ReplayGain[/white]\n" + "=" * 50)

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
        logging.info(f"\n--- Processing Album: [bold cyan]{album_name}[/bold cyan] ({len(album_files)} tracks) ---")
        process_album(album_files)


def report(args):
    """
    Regenerate an HTML report from a previously saved JSON data file.
    """
    from pathlib import Path
    from flac_toolkit.dataframe import load_report_data, create_dataframe, generate_html_report

    json_path = Path(args.json_file)
    if not json_path.exists():
        logging.error(f"File not found: {json_path}")
        return

    results, duplicate_groups = load_report_data(json_path)

    output_html = args.output or str(json_path.with_suffix('.html'))

    logging.info("Generating HTML report...")
    df = create_dataframe(results)
    generate_html_report(df, Path(output_html), duplicate_groups=duplicate_groups)


def main():
    from flac_toolkit.core import setup_logging

    parser = argparse.ArgumentParser(
        prog='flac_toolkit',
        description='FLAC Toolkit - RFC 9639 validation, repair, ReplayGain, and duplicate detection.'
    )

    # Global options
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose (debug) output.')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress all output except errors.')

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # Validate command (primary)
    validate_parser = subparsers.add_parser('validate', help='Validate FLAC files against RFC 9639 specification and generate HTML report.')
    validate_parser.add_argument('target_paths', nargs='+', help='One or more files or directories to process.')
    validate_parser.add_argument('-w', '--workers', type=int, default=None, help='Number of parallel workers.')
    validate_parser.add_argument('-o', '--output', type=str, default='flac_validation_report.html', help='Path to the output HTML report.')
    validate_parser.add_argument('--check-duplicates', action='store_true', help='Also detect audio duplicates and include a Duplicates tab in the HTML report. Reuses MD5s already computed during validation (no extra I/O).')

    # Repair command
    repair_parser = subparsers.add_parser('repair', help='Repair files based on validation. Use --force to re-encode all.')
    repair_parser.add_argument('target_paths', nargs='+', help='One or more files or directories to process.')
    repair_parser.add_argument('--force', action='store_true', help='Force re-encoding on all files.')
    repair_parser.add_argument('--no-backup', action='store_true', help='Delete original files instead of quarantining (saves disk space).')
    repair_parser.add_argument('-w', '--workers', type=int, default=None, help='Number of parallel workers.')

    # ReplayGain command
    replaygain_parser = subparsers.add_parser('replaygain', help='Calculate and apply ReplayGain tags.')
    replaygain_parser.add_argument('target_paths', nargs='+', help='One or more files or directories to process.')
    replaygain_parser.add_argument('--assume-album', action='store_true', help='Treat all files as one album.')

    # Report command (regenerate from JSON)
    report_parser = subparsers.add_parser('report', help='Regenerate an HTML report from a previously saved JSON data file (no re-scan required).')
    report_parser.add_argument('json_file', help='Path to the .json report data file produced by a previous validate run.')
    report_parser.add_argument('-o', '--output', type=str, default=None, help='Path to the output HTML report (default: same name as JSON with .html extension).')

    args = parser.parse_args()

    # Setup logging based on global flags
    setup_logging(args.verbose, args.quiet)

    # Dispatch to the appropriate command
    if args.command == 'validate':
        validate(args)
    elif args.command == 'repair':
        repair(args)
    elif args.command == 'replaygain':
        replaygain(args)
    elif args.command == 'report':
        report(args)


if __name__ == "__main__":
    main()