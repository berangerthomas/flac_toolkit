import struct
import hashlib
import re
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from mutagen.flac import FLAC, FLACNoHeaderError
from mutagen.mp3 import HeaderNotFoundError
from pathvalidate import validate_filename, ValidationError

from flac_toolkit.constants import (
    PADDING_BLOCK_TYPE, PADDING_SIZE_THRESHOLD_BYTES
)


def analyze_flac_comprehensive(file_path: Path) -> Dict[str, Any]:
    """Performs a comprehensive analysis of a FLAC file using multiple techniques."""
    result: Dict[str, Any] = {
        'file': str(file_path), 'status': 'INVALID', 'errors': [], 'warnings': [],
        'info': {}, 'metrics': {}, 'tags': {}, 'header_analysis': {}, 'data_structure_analysis': {},
        'repair_suggestions': []
    }

    header_analysis = _check_file_header_manually(file_path)
    result['header_analysis'] = header_analysis
    if header_analysis['errors']:
        result['errors'].extend([f"Header Error: {e}" for e in header_analysis['errors']])
    
    result['errors'].extend(_analyze_metadata_blocks(header_analysis['metadata_blocks']))

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
        elif not md5_header:
            result['errors'].append("MD5 signature is unset (0) in header.")

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

        data_analysis = _analyze_data_structure(file_path, audio.info)
        result['data_structure_analysis'] = data_analysis
        result['errors'].extend(data_analysis['errors'])
        result['warnings'].extend(data_analysis['warnings'])
        
        result['warnings'].extend(_analyze_filename_compatibility(file_path.name))

    except (FLACNoHeaderError, HeaderNotFoundError) as e:
        result['errors'].append(f"Structure Error: {e}")
    except Exception as e:
        result['errors'].append(f"Generic Error: {e}")
    
    if not result['errors']:
        if result['warnings']:
            result['status'] = 'VALID (with warnings)'
        else:
            result['status'] = 'VALID'
    
    result['repair_suggestions'] = _generate_repair_suggestions(result)
    
    return result

def _check_file_header_manually(file_path: Path) -> Dict[str, Any]:
        header_info: Dict[str, Any] = {'is_flac': False, 'metadata_blocks': [], 'errors': []}
        try:
            with open(file_path, 'rb') as f:
                if f.read(4) == b'fLaC':
                    header_info['is_flac'] = True
                    while True:
                        block_header = f.read(4)
                        if len(block_header) < 4:
                            header_info['errors'].append("Unexpected end of file while reading a block header.")
                            break
                        is_last = (block_header[0] & 0x80) != 0
                        block_type = block_header[0] & 0x7F
                        length = struct.unpack('>I', b'\x00' + block_header[1:4])[0]
                        header_info['metadata_blocks'].append({'type': block_type, 'length': length, 'is_last': is_last})
                        f.seek(length, 1)
                        if is_last: break
                else:
                    header_info['is_flac'] = False
                    header_info['errors'].append("Signature 'fLaC' not found at the beginning of the file.")
        except Exception as e:
            header_info['errors'].append(f"Low-level read error: {e}")
        return header_info

def _analyze_metadata_blocks(blocks: List[Dict[str, Any]]) -> List[str]:
    """Analyzes the list of metadata blocks for structural anomalies."""
    errors = []
    
    # Check for STREAMINFO (Type 0)
    if not any(b['type'] == 0 for b in blocks):
        errors.append("Critical: STREAMINFO block missing")

    for block in blocks:
        # Check PADDING size
        if block['type'] == PADDING_BLOCK_TYPE and block['length'] > PADDING_SIZE_THRESHOLD_BYTES:
            errors.append(f"Metadata Error: PADDING block with abnormal size detected ({block['length'] / 1024:.0f} KB). This indicates probable corruption.")
        
        # Check SEEKTABLE (Type 3) validity
        if block['type'] == 3:
            if block['length'] % 18 != 0:
                errors.append(f"Metadata Error: SEEKTABLE has invalid size ({block['length']} bytes), must be multiple of 18.")

    return errors

def _analyze_filename_compatibility(filename: str) -> List[str]:
    """Analyzes filename for cross-platform compatibility."""
    warnings = []
    try:
        validate_filename(filename, platform="universal")
    except ValidationError as e:
        msg = str(e)
        # Remove the value field which contains the filename to keep the report clean
        # Matches: , value='...' or , value="..."
        msg = re.sub(r",?\s*value=(['\"]).*?\1", "", msg)
        warnings.append(f"Filename Warning: {msg}")
    return warnings

def _analyze_data_structure(file_path: Path, audio_info) -> Dict[str, Any]:
        analysis = {'errors': [], 'warnings': [], 'data_start_offset': 'N/A', 'expected_uncompressed_size': 'N/A', 'actual_compressed_size': 'N/A'}
        if hasattr(audio_info, 'total_samples') and hasattr(audio_info, 'channels') and hasattr(audio_info, 'bits_per_sample'):
             analysis['expected_uncompressed_size'] = (audio_info.total_samples * audio_info.channels * (audio_info.bits_per_sample // 8))
        
        return analysis


def _calculate_audio_md5(file_path: Path, bits_per_sample: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Calculates the MD5 of the raw audio samples using soundfile and numpy.
    Returns (md5_hex, error_message).
    """
    md5 = hashlib.md5()
    block_size = 65536
    
    try:
        # soundfile reads into numpy arrays.
        # FLAC MD5 is calculated on signed little-endian samples.
        
        if bits_per_sample == 16:
            dtype = 'int16'
            with sf.SoundFile(file_path) as f:
                for block in f.blocks(blocksize=block_size, dtype=dtype, always_2d=True):
                    # int16 is already correct representation
                    md5.update(block.tobytes())
                    
        elif bits_per_sample == 24:
            # 24-bit depth soundfile reads as int32 (scaled).
            # We need to shift right by 8 to get original 24-bit values.
            # Then pack into 3 bytes (Little Endian).
            dtype = 'int32'
            with sf.SoundFile(file_path) as f:
                for block in f.blocks(blocksize=block_size, dtype=dtype, always_2d=True):
                    # Shift right to restore 24-bit values
                    # Note: soundfile scales 24-bit to 32-bit by left-shifting 8 bits.
                    # So we right shift 8 bits.
                    raw_24 = block.astype(np.int32) >> 8
                    bytes_view = raw_24.view(np.uint8).reshape(-1, 4)
                    packed_24 = bytes_view[:, :3].tobytes()
                    md5.update(packed_24)
        else:
             return None, f"MD5 calculation not implemented for {bits_per_sample}-bit depth."

        return md5.hexdigest(), None

    except Exception as e:
        return None, str(e)

def _generate_repair_suggestions(result: Dict[str, Any]) -> List[Dict[str, str]]:
        suggestions = []
        if result['status'] == 'INVALID':
            suggestions.append({'action': 'reencode', 'reason': 'Structural corruption detected.'})
        elif result['warnings']:
            if any('Filename' in w for w in result['warnings']):
                 suggestions.append({'action': 'rename', 'reason': 'Non-standard filename.'})
        return suggestions
