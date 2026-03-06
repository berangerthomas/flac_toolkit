"""
flac_toolkit/analyzer.py
Comprehensive FLAC file analysis with RFC 9639 validation.
"""

import hashlib
import re
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from mutagen.flac import FLAC, FLACNoHeaderError
from mutagen.mp3 import HeaderNotFoundError
from pathvalidate import validate_filename, ValidationError

from flac_toolkit.validator import RFC9639Validator


def analyze_flac_comprehensive(file_path: Path) -> Dict[str, Any]:
    """Performs a comprehensive analysis of a FLAC file using multiple techniques."""
    result: Dict[str, Any] = {
        'file': str(file_path), 'status': 'INVALID', 'errors': [], 'warnings': [],
        'info': {}, 'metrics': {}, 'tags': {},
        'repair_suggestions': [], 'rfc9639': {}
    }

    # Run RFC 9639 validation first
    validator = RFC9639Validator(file_path)
    validation_result = validator.validate()
    
    # Store RFC 9639 results for detailed report popup
    result['rfc9639'] = validation_result.to_dict()
    
    # Copy RFC 9639 errors/warnings to main result
    for e in validation_result.errors:
        result['errors'].append(f"[{e.code}] {e.message}")
    for w in validation_result.warnings:
        result['warnings'].append(f"[{w.code}] {w.message}")

    try:
        audio = FLAC(file_path)
        
        # Formatted info for display
        result['info'] = {
            'duration': f"{audio.info.length:.2f}s", 
            'sample_rate': audio.info.sample_rate,
            'channels': audio.info.channels, 
            'bits_per_sample': audio.info.bits_per_sample,
            'bitrate': f"{audio.info.bitrate // 1000} kbps"
        }

        # Raw metrics for DataFrame/Reporting
        md5_header = format(audio.info.md5_signature, '032x') if audio.info.md5_signature else None
        
        # Calculate MD5 (Pure Python)
        md5_calculated, md5_error = _calculate_audio_md5(file_path, audio.info.bits_per_sample)
        
        result['metrics'] = {
            'duration_seconds': audio.info.length,
            'sample_rate': audio.info.sample_rate,
            'channels': audio.info.channels,
            'bits_per_sample': audio.info.bits_per_sample,
            'bitrate_kbps': int(audio.info.bitrate / 1000) if audio.info.bitrate else 0,
            'filesize_mb': round(file_path.stat().st_size / (1024 * 1024), 2),
            'md5_header': md5_header,
            'md5_calculated': md5_calculated
        }
        
        if md5_error:
            result['errors'].append(f"MD5 Calculation Error: {md5_error}")
        elif md5_header and md5_calculated and md5_header != md5_calculated:
            result['errors'].append(f"MD5 Mismatch: Header={md5_header}, Calculated={md5_calculated}")

        # Metadata tags
        tags: Any = audio.tags if audio.tags else {}
        result['tags'] = {
            'artist': (tags.get('artist') or [''])[0],
            'album': (tags.get('album') or [''])[0],
            'title': (tags.get('title') or [''])[0],
            'genre': (tags.get('genre') or [''])[0],
            'date': (tags.get('date') or [''])[0],
            'tracknumber': (tags.get('tracknumber') or [''])[0],
            'albumartist': (tags.get('albumartist') or [''])[0],
            'replaygain_track_gain': (tags.get('replaygain_track_gain') or [''])[0],
            'replaygain_track_peak': (tags.get('replaygain_track_peak') or [''])[0],
        }

        result['warnings'].extend(_analyze_filename_compatibility(file_path.name))

    except (FLACNoHeaderError, HeaderNotFoundError) as e:
        result['errors'].append(f"Structure Error: {e}")
    except Exception as e:
        result['errors'].append(f"Generic Error: {e}")
    
    # Determine status based on RFC 9639 validation
    if validation_result.is_valid:
        if result['warnings']:
            result['status'] = 'VALID (with warnings)'
        else:
            result['status'] = 'VALID'
    else:
        result['status'] = 'INVALID'
    
    result['repair_suggestions'] = _generate_repair_suggestions(result)
    
    return result


def _analyze_filename_compatibility(filename: str) -> List[str]:
    """Analyzes filename for cross-platform compatibility."""
    warnings: List[str] = []
    try:
        validate_filename(filename, platform="universal")
    except ValidationError as e:
        msg = str(e)
        msg = re.sub(r",?\s*value=(['\"]).*?\1", "", msg)
        warnings.append(f"Filename Warning: {msg}")
    return warnings


def _calculate_audio_md5(file_path: Path, bits_per_sample: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Calculates the MD5 of the raw audio samples using soundfile and numpy.
    FLAC MD5 is computed over signed little-endian interleaved samples.
    Supports all standard bit depths: 8, 16, 20, 24, 32.
    Returns (md5_hex, error_message).
    """
    md5 = hashlib.md5()
    block_size = 65536
    bytes_per_sample = (bits_per_sample + 7) // 8  # 1, 2, 3, 3, 4

    try:
        if bits_per_sample <= 16:
            # 8-bit and 16-bit: soundfile reads as int16 natively
            dtype = 'int16'
            with sf.SoundFile(file_path) as f:
                for block in f.blocks(blocksize=block_size, dtype=dtype, always_2d=True):
                    if bits_per_sample == 8:
                        # FLAC 8-bit is signed: soundfile int16 scaled by 256, shift back
                        samples_8 = (block >> 8).astype(np.int8)
                        md5.update(samples_8.tobytes())
                    else:
                        md5.update(block.tobytes())

        elif bits_per_sample <= 24:
            # 20-bit and 24-bit: soundfile reads as int32 (left-shifted by 8 bits)
            dtype = 'int32'
            shift = 32 - bits_per_sample  # 12 for 20-bit, 8 for 24-bit
            with sf.SoundFile(file_path) as f:
                for block in f.blocks(blocksize=block_size, dtype=dtype, always_2d=True):
                    raw = block.astype(np.int32) >> shift
                    # Pack to 3 bytes LE per sample (FLAC packs 20-bit and 24-bit in 3 bytes)
                    bytes_view = raw.view(np.uint8).reshape(-1, 4)
                    packed = bytes_view[:, :3].tobytes()
                    md5.update(packed)

        elif bits_per_sample == 32:
            # 32-bit: soundfile reads as int32
            dtype = 'int32'
            with sf.SoundFile(file_path) as f:
                for block in f.blocks(blocksize=block_size, dtype=dtype, always_2d=True):
                    md5.update(block.tobytes())

        else:
            return None, f"MD5 calculation not supported for {bits_per_sample}-bit depth."

        return md5.hexdigest(), None

    except Exception as e:
        error_msg = str(e)
        if "psf_fseek" in error_msg or "psf_fread" in error_msg:
            error_msg = f"libsndfile I/O error (file may be corrupted or truncated): {error_msg}"
        return None, error_msg


def _generate_repair_suggestions(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate repair suggestions based on analysis result."""
    suggestions: List[Dict[str, str]] = []
    if result['status'] == 'INVALID':
        suggestions.append({'action': 'reencode', 'reason': 'Structural corruption detected.'})
    elif result['warnings']:
        if any('Filename' in w for w in result['warnings']):
            suggestions.append({'action': 'rename', 'reason': 'Non-standard filename.'})
    return suggestions