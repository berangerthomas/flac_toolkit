import logging
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from mutagen.flac import FLAC

from flac_toolkit.constants import TARGET_LOUDNESS_LUFS



def _normalize_audio_data(data: np.ndarray) -> np.ndarray:
    """Converts audio data to 32-bit float, handling integers."""
    original_dtype = data.dtype
    if np.issubdtype(original_dtype, np.integer):
        max_val = np.iinfo(original_dtype).max
        return data.astype(np.float32) / max_val
    elif np.issubdtype(original_dtype, np.floating):
        return data.astype(np.float32)
    else:
        raise TypeError(f"Unsupported audio data type: {original_dtype}")

def _calculate_track_replaygain(file_path: Path) -> Tuple[float, float, np.ndarray] | None:
    """Calculates loudness, peak, and returns the raw audio data to avoid re-reading."""
    try:
        data, rate = sf.read(file_path, always_2d=True)
        float_data = _normalize_audio_data(data)

        meter = pyln.Meter(rate)
        loudness = meter.integrated_loudness(float_data)
        peak = np.max(np.abs(float_data))
        return loudness, peak, data
    except Exception as e:
        logging.error(f"✗ Failed to analyze track {file_path.name}: {e}")
        return None

def process_album(album_files: List[Path]):
    """
    Calculates and applies track and album ReplayGain to a list of files.
    """
    track_data = {}
    all_audio_data = []

    # 1. Calculate track gain for each file
    for file_path in album_files:
        result = _calculate_track_replaygain(file_path)
        if result:
            loudness, peak, audio_data = result
            track_data[file_path] = (loudness, peak)
            all_audio_data.append(audio_data)

    if not all_audio_data:
        logging.warning("✗ No valid tracks found to process for album gain.")
        return

    # 2. Calculate album gain
    try:
        # Normalize each track before concatenating
        normalized_album_data = [_normalize_audio_data(d) for d in all_audio_data]
        concatenated_data = np.concatenate(normalized_album_data)
        
        rate = sf.info(album_files[0]).samplerate
        meter = pyln.Meter(rate)
        album_loudness = meter.integrated_loudness(concatenated_data)
        album_peak = max(peak for _, peak in track_data.values())
        
        album_gain_db = TARGET_LOUDNESS_LUFS - album_loudness
        album_gain_str = f"{album_gain_db:+.2f} dB"
        album_peak_str = f"{album_peak:.6f}"
        logging.info(f"✓ Album Gain Calculated: {album_gain_str} for {len(album_files)} tracks.")
    except Exception as e:
        logging.error(f"✗ Failed to calculate album gain: {e}")
        return

    # 3. Apply all tags
    for file_path, (loudness, peak) in track_data.items():
        try:
            track_gain_db = TARGET_LOUDNESS_LUFS - loudness
            track_gain_str = f"{track_gain_db:+.2f} dB"
            track_peak_str = f"{peak:.6f}"

            audio = FLAC(file_path)
            audio["REPLAYGAIN_TRACK_GAIN"] = track_gain_str
            audio["REPLAYGAIN_TRACK_PEAK"] = track_peak_str
            audio["REPLAYGAIN_ALBUM_GAIN"] = album_gain_str
            audio["REPLAYGAIN_ALBUM_PEAK"] = album_peak_str
            audio.save()
            logging.info(f"  ✓ Tags applied to {file_path.name}")
        except Exception as e:
            logging.error(f"✗ Failed to apply tags to {file_path.name}: {e}")
