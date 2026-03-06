import re
import shutil
import subprocess
import logging
import uuid
from pathlib import Path

from mutagen.flac import FLAC
from unidecode import unidecode
from pathvalidate import sanitize_filename

from flac_toolkit.constants import QUARANTINE_FOLDER_NAME


def repair_worker(file_path: Path, force: bool, no_backup: bool):
    """Process a single file for repair: analyze, then reencode/rename as needed."""
    from flac_toolkit.analyzer import analyze_flac_comprehensive

    if force:
        reencode_flac(file_path, no_backup=no_backup)
        return

    analysis = analyze_flac_comprehensive(file_path)
    if not analysis['repair_suggestions']:
        logging.debug(f"Skipping (valid): {file_path.name}")
        return

    logging.debug(f"Issues found in: {file_path.name}")
    for suggestion in analysis['repair_suggestions']:
        if suggestion['action'] == 'reencode':
            reencode_flac(file_path, no_backup=no_backup)
        elif suggestion['action'] == 'rename':
            repair_filename(file_path)



def repair_filename(file_path: Path) -> Path:
    original_name = file_path.name
    repaired_name = unidecode(original_name)
    repaired_name = sanitize_filename(repaired_name, platform="universal")

    if repaired_name != original_name:
        new_path = file_path.with_name(repaired_name)
        try:
            file_path.rename(new_path)
            logging.debug(f"[green]✓[/green] Renamed: [cyan]{original_name}[/cyan] → [bold green]{repaired_name}[/bold green]")
            return new_path
        except Exception as e:
            logging.error(f"[red]✗[/red] Rename error: {e}")
    return file_path

def reencode_flac(input_path: Path, no_backup: bool = False) -> Path | None:
    # Use a short temporary filename in the same directory to avoid path length limits
    # This is especially important on Windows where MAX_PATH is 260 characters
    short_id = uuid.uuid4().hex[:8]
    temp_output_path = input_path.parent / f"flac_repair_{short_id}.flac"
    success = False
    last_error = ""

    try:
        if shutil.which('flac'):
            cmd = ['flac', '--best', '--verify', '--force', '-o', str(temp_output_path), str(input_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0:
                logging.debug(f"[green]✓[/green] Re-encoded ([bold]flac[/bold]): [cyan]{input_path.name}[/cyan]")
                success = True
            else:
                last_error = result.stderr.strip()
                logging.error(f"[red]✗[/red] Re-encode failed ([bold]flac[/bold]): {last_error}")
        elif shutil.which('ffmpeg'):
            logging.debug("→ Attempting with [bold]ffmpeg[/bold]...")
            # Use maximum compression settings equivalent to flac --best (level 8)
            cmd = ['ffmpeg', '-i', str(input_path), '-acodec', 'flac', '-compression_level', '12', '-y', str(temp_output_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0:
                logging.debug(f"[green]✓[/green] Re-encoded ([bold]ffmpeg[/bold]): [cyan]{input_path.name}[/cyan]")
                success = True
            else:
                last_error = result.stderr.strip()
                logging.error(f"[red]✗[/red] Re-encode failed ([bold]ffmpeg[/bold]): {last_error}")
        
        if not success:
            logging.error("[red]✗[/red] No functional re-encoding tool ([bold]flac, ffmpeg[/bold]) found or encoding failed.")
            
            # Log the failure and accumulate the command line to a retry script
            log_file = "failed_repairs_retry.bat"
            try:
                import sys
                
                # Format error lines as batch comments
                error_comments = ""
                if last_error:
                    error_comments = "\n".join([f":: {line}" for line in last_error.splitlines()])
                    error_comments = f"\n{error_comments}\n"
                else:
                    error_comments = "\n"

                retry_content = (
                    f":: Failed file: {input_path.name}{error_comments}"
                    f"\"{sys.executable}\" \"{Path(sys.argv[0]).resolve()}\" repair -w 1 --force \"{input_path}\"\n\n"
                )
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(retry_content)
            except Exception as e:
                logging.debug(f"Failed to record failure in {log_file}: {e}")
                
            # Clean up temp file if it was created
            if temp_output_path.exists():
                temp_output_path.unlink()
            return None

        # Post-processing: Metadata copy and Swap
        _copy_metadata(input_path, temp_output_path)
        
        if no_backup:
            # Delete original file directly (no backup)
            try:
                input_path.unlink()
                logging.debug(f"  [green]✓[/green] Deleted original (no-backup mode): [cyan]{input_path.name}[/cyan]")
            except OSError as e:
                logging.warning(f"  [yellow]⚠[/yellow] Failed to delete original: {e}")
            try:
                temp_output_path.rename(input_path)
                logging.debug(f"  [green]✓[/green] Renamed repaired file to original name: [cyan]{input_path.name}[/cyan]")
                return input_path
            except OSError as e:
                logging.error(f"  [red]✗[/red] Failed to rename repaired file to original name: {e}")
                return temp_output_path
        else:
            # Default behavior: quarantine original
            if _quarantine_original(input_path):
                try:
                    temp_output_path.rename(input_path)
                    logging.debug(f"  [green]✓[/green] Renamed repaired file to original name: [cyan]{input_path.name}[/cyan]")
                    return input_path
                except OSError as e:
                    logging.error(f"  [red]✗[/red] Failed to rename repaired file to original name: {e}")
                    return temp_output_path
            else:
                logging.warning("  [yellow]⚠[/yellow] Quarantine failed, keeping repaired file with temp name.")
                return temp_output_path
    except Exception as e:
        # Clean up temp file on any unexpected error
        if temp_output_path.exists():
            temp_output_path.unlink()
        logging.error(f"✗ Unexpected error during re-encoding: {e}")
        return None

def _quarantine_original(file_path: Path) -> bool:
    """Moves the original file to a quarantine folder. Returns True if successful."""
    try:
        quarantine_dir = file_path.parent / QUARANTINE_FOLDER_NAME
        quarantine_dir.mkdir(exist_ok=True)
        destination = quarantine_dir / file_path.name
        
        if destination.exists():
            destination.unlink()
            
        shutil.move(str(file_path), str(destination))
        logging.debug(f"  [green]✓[/green] Moved original to quarantine: [bold]{QUARANTINE_FOLDER_NAME}[/bold]/[cyan]{file_path.name}[/cyan]")
        return True
    except Exception as e:
        logging.warning(f"  [yellow]⚠[/yellow] Failed to move original to quarantine: {e}")
        return False

def _copy_metadata(source: Path, dest: Path):
    try:
        original = FLAC(source); repaired = FLAC(dest)
        repaired.clear(); repaired.update(original); repaired.save()
        logging.debug("  [green]✓[/green] Copied metadata.")
    except Exception as e:
        logging.warning(f"  [yellow]⚠[/yellow] Failed to copy metadata: {e}")
