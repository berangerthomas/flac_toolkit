import re
import shutil
import subprocess
import logging
from pathlib import Path

from mutagen.flac import FLAC
from unidecode import unidecode
from pathvalidate import sanitize_filename

from flac_toolkit.constants import QUARANTINE_FOLDER_NAME



def repair_filename(file_path: Path) -> Path:
    original_name = file_path.name
    repaired_name = unidecode(original_name)
    repaired_name = sanitize_filename(repaired_name, platform="universal")

    if repaired_name != original_name:
        new_path = file_path.with_name(repaired_name)
        try:
            file_path.rename(new_path)
            logging.info(f"✓ Renamed: {original_name} → {repaired_name}")
            return new_path
        except Exception as e:
            logging.error(f"✗ Rename error: {e}")
    return file_path

def reencode_flac(input_path: Path, no_backup: bool = False) -> Path | None:
    # Use a temporary name for the repair process
    temp_output_path = input_path.with_stem(f"{input_path.stem}_repaired")
    success = False

    if shutil.which('flac'):
        cmd = ['flac', '--best', '--verify', '--force', '-o', str(temp_output_path), str(input_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            logging.info(f"✓ Re-encoded (flac): {temp_output_path.name}")
            success = True
        else:
            logging.error(f"✗ Re-encode failed (flac): {result.stderr.strip()}")
    elif shutil.which('ffmpeg'):
        logging.info("→ Attempting with ffmpeg...")
        cmd = ['ffmpeg', '-i', str(input_path), '-acodec', 'flac', '-y', str(temp_output_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            logging.info(f"✓ Re-encoded (ffmpeg): {temp_output_path.name}")
            success = True
        else:
            logging.error(f"✗ Re-encode failed (ffmpeg): {result.stderr.strip()}")
    
    if not success:
        logging.error("✗ No functional re-encoding tool (flac, ffmpeg) found or encoding failed.")
        return None

    # Post-processing: Metadata copy and Swap
    _copy_metadata(input_path, temp_output_path)
    
    if no_backup:
        # Delete original file directly (no backup)
        try:
            input_path.unlink()
            logging.info(f"  ✓ Deleted original (no-backup mode): {input_path.name}")
        except OSError as e:
            logging.warning(f"  ⚠ Failed to delete original: {e}")
        try:
            temp_output_path.rename(input_path)
            logging.info(f"  ✓ Renamed repaired file to original name: {input_path.name}")
            return input_path
        except OSError as e:
            logging.error(f"  ✗ Failed to rename repaired file to original name: {e}")
            return temp_output_path
    else:
        # Default behavior: quarantine original
        if _quarantine_original(input_path):
            try:
                temp_output_path.rename(input_path)
                logging.info(f"  ✓ Renamed repaired file to original name: {input_path.name}")
                return input_path
            except OSError as e:
                logging.error(f"  ✗ Failed to rename repaired file to original name: {e}")
                return temp_output_path
        else:
            logging.warning("  ⚠ Quarantine failed, keeping repaired file with '_repaired' suffix.")
            return temp_output_path

def _quarantine_original(file_path: Path) -> bool:
    """Moves the original file to a quarantine folder. Returns True if successful."""
    try:
        quarantine_dir = file_path.parent / QUARANTINE_FOLDER_NAME
        quarantine_dir.mkdir(exist_ok=True)
        destination = quarantine_dir / file_path.name
        
        if destination.exists():
            destination.unlink()
            
        shutil.move(str(file_path), str(destination))
        logging.info(f"  ✓ Moved original to quarantine: {QUARANTINE_FOLDER_NAME}/{file_path.name}")
        return True
    except Exception as e:
        logging.warning(f"  ⚠ Failed to move original to quarantine: {e}")
        return False

def _copy_metadata(source: Path, dest: Path):
    try:
        original = FLAC(source); repaired = FLAC(dest)
        repaired.clear(); repaired.update(original); repaired.save()
        logging.info("  ✓ Copied metadata.")
    except Exception as e:
        logging.warning(f"  ⚠ Failed to copy metadata: {e}")
