import logging
import typer
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict
from mutagen.flac import FLAC

from flac_toolkit.core import find_flac_files, setup_logging
from flac_toolkit.analyzer import analyze_flac_comprehensive
from flac_toolkit.repair import repair_filename, reencode_flac
from flac_toolkit.replaygain import process_album
from flac_toolkit.reporter import print_analysis_result, print_summary
from flac_toolkit.dataframe import create_dataframe, generate_html_report
from tqdm import tqdm

app = typer.Typer(help="FLAC Toolkit - Advanced diagnosis, repair, and ReplayGain tool.")

@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose (debug) output."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress all output except errors.")
):
    """
    Global configuration callback.
    """
    setup_logging(verbose, quiet)

@app.command()
def analyze(
    target_paths: List[Path] = typer.Argument(..., help="One or more files or directories to process."),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers."),
    output_html: Path = typer.Option(Path("flac_analysis_report.html"), "--output", "-o", help="Path to the output HTML report.")
):
    """
    Perform an in-depth analysis of each file and generate an HTML report.
    """
    logging.info("ANALYZE Mode - In-depth analysis\n" + "=" * 50)
    
    files = list(find_flac_files(target_paths))
    if not files:
        logging.warning("No FLAC files found.")
        return

    # Parallel analysis
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(tqdm(executor.map(analyze_flac_comprehensive, files), total=len(files), unit="file"))
    
    # Console Output
    for r in results:
        print_analysis_result(r)
    print_summary(results)

    # Generate HTML Report
    logging.info("\nGenerating HTML report...")
    df = create_dataframe(results)
    generate_html_report(df, output_html)


@app.command()
def repair(
    target_paths: List[Path] = typer.Argument(..., help="One or more files or directories to process."),
    force: bool = typer.Option(False, "--force", help="Force re-encoding on all files."),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers.")
):
    """
    Repair files based on analysis. Use --force to re-encode all.
    """
    if force:
        logging.info("REPAIR Mode (Forced) - Re-encoding all files\n" + "=" * 50)
    else:
        logging.info("REPAIR Mode (Auto) - Analyzing and repairing problematic files\n" + "=" * 50)

    files = list(find_flac_files(target_paths))
    if not files:
        logging.warning("No FLAC files found.")
        return

    def repair_worker(file_path: Path):
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

    with ProcessPoolExecutor(max_workers=workers) as executor:
        list(tqdm(executor.map(repair_worker, files), total=len(files), unit="file", desc="Processing"))

    logging.info("\nRepair process completed.")

@app.command()
def replaygain(
    target_paths: List[Path] = typer.Argument(..., help="One or more files or directories to process."),
    assume_album: bool = typer.Option(False, "--assume-album", help="Treat all files as one album.")
):
    """
    Calculate and apply ReplayGain tags.
    """
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


if __name__ == "__main__":
    app()
