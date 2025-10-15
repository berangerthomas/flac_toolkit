#!/usr/bin/env python3
"""
FLAC Toolkit - Advanced FLAC Diagnosis and Repair Tool (Final Version)
Integrates expert analysis of metadata anomalies for precise diagnostics.

Usage:
    python flac_toolkit.py analyze <target(s)...>
    python flac_toolkit.py auto <target(s)...>
    python flac_toolkit.py repair <target(s)...>
"""

import os
import sys
import re
import subprocess
import struct
import argparse
import shutil
from pathlib import Path
from typing import List, Dict, Any, Iterator

# --- Third-party dependencies ---
try:
    from mutagen.flac import FLAC, FLACNoHeaderError
    from mutagen.mp3 import HeaderNotFoundError
    from unidecode import unidecode
except ImportError as e:
    print(f"Error: Missing dependency - {e}", file=sys.stderr)
    print("Please install the required packages: pip install mutagen unidecode", file=sys.stderr)
    sys.exit(1)


class FLACToolkit:
    """A comprehensive tool to diagnose, analyze, and repair FLAC files."""

    def __init__(self):
        self.repair_log: List[str] = []

    def analyze_flac_comprehensive(self, file_path: Path) -> Dict[str, Any]:
        """Performs a comprehensive analysis of a FLAC file using multiple techniques."""
        result: Dict[str, Any] = {
            'file': str(file_path), 'status': 'INVALID', 'errors': [], 'warnings': [],
            'info': {}, 'header_analysis': {}, 'data_structure_analysis': {},
            'repair_suggestions': []
        }

        header_analysis = self._check_file_header_manually(file_path)
        result['header_analysis'] = header_analysis
        if header_analysis['errors']:
            result['errors'].extend([f"Header Error: {e}" for e in header_analysis['errors']])
        
        result['errors'].extend(self._analyze_metadata_blocks(header_analysis['metadata_blocks']))

        try:
            audio = FLAC(file_path)
            result['info'] = {
                'duration': f"{audio.info.length:.2f}s", 'sample_rate': audio.info.sample_rate,
                'channels': audio.info.channels, 'bits_per_sample': audio.info.bits_per_sample,
                'bitrate': f"{audio.info.bitrate // 1000} kbps"
            }

            data_analysis = self._analyze_data_structure(file_path, audio.info)
            result['data_structure_analysis'] = data_analysis
            result['errors'].extend(data_analysis['errors'])
            result['warnings'].extend(data_analysis['warnings'])
            
            result['warnings'].extend(self._analyze_filename_compatibility(file_path.name))
            result['warnings'].extend(self._check_android_compatibility(audio.info))

        except (FLACNoHeaderError, HeaderNotFoundError) as e:
            result['errors'].append(f"Structure Error: {e}")
        except Exception as e:
            result['errors'].append(f"Generic Error: {e}")
        
        if not result['errors']:
            if result['warnings']:
                result['status'] = 'VALID (with warnings)'
            else:
                result['status'] = 'VALID'
        
        result['repair_suggestions'] = self._generate_repair_suggestions(result)
        
        return result

    def _check_file_header_manually(self, file_path: Path) -> Dict[str, Any]:
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

    def _analyze_metadata_blocks(self, blocks: List[Dict[str, Any]]) -> List[str]:
        """Analyzes the list of metadata blocks for structural anomalies."""
        errors = []
        PADDING_SIZE_THRESHOLD = 131072  # 128 KB
        for block in blocks:
            if block['type'] == 1 and block['length'] > PADDING_SIZE_THRESHOLD:
                errors.append(f"Metadata Error: PADDING block with abnormal size detected ({block['length'] / 1024:.0f} KB). This indicates probable corruption.")
        return errors

    def _analyze_filename_compatibility(self, filename: str) -> List[str]:
        warnings = []
        if any(c in filename for c in ['<', '>', ':', '"', '|', '?', '*', '\0']):
            warnings.append("Filename Warning: Contains non-standard characters.")
        if len(filename) > 255:
            warnings.append("Filename Warning: Excessively long filename.")
        return warnings

    def _analyze_data_structure(self, file_path: Path, audio_info) -> Dict[str, Any]:
        analysis = {'errors': [], 'warnings': [], 'data_start_offset': 'N/A', 'expected_uncompressed_size': 'N/A', 'actual_compressed_size': 'N/A'}
        if hasattr(audio_info, 'data_start'):
            analysis['data_start_offset'] = audio_info.data_start
            analysis['expected_uncompressed_size'] = (audio_info.total_samples * audio_info.channels * (audio_info.bits_per_sample // 8))
            analysis['actual_compressed_size'] = file_path.stat().st_size - audio_info.data_start
            if analysis['actual_compressed_size'] <= 0:
                analysis['errors'].append("Data Error: File appears to contain no audio data (size <= 0).")
        else:
            analysis['warnings'].append("Data Warning: Could not locate the start of audio data (non-standard structure). The file may still be playable.")
        return analysis

    def _check_android_compatibility(self, audio_info) -> List[str]:
        warnings = []
        if audio_info.sample_rate > 48000:
            warnings.append("Android Compat Warning: Sample rate > 48kHz.")
        if audio_info.channels > 2:
            warnings.append("Android Compat Warning: More than 2 audio channels (multi-channel).")
        if audio_info.bits_per_sample > 16:
            warnings.append("Android Compat Warning: Bit depth > 16-bit.")
        return warnings

    def _generate_repair_suggestions(self, result: Dict[str, Any]) -> List[Dict[str, str]]:
        suggestions = []
        if result['status'] == 'INVALID':
            suggestions.append({'action': 'reencode', 'reason': 'Structural corruption detected.'})
        elif result['warnings']:
            if any('Android' in w for w in result['warnings']):
                 suggestions.append({'action': 'reencode', 'reason': 'Standardize for compatibility.'})
            if any('Filename' in w for w in result['warnings']):
                 suggestions.append({'action': 'rename', 'reason': 'Non-standard filename.'})
        return suggestions

    def repair_filename(self, file_path: Path) -> Path:
        original_name = file_path.name
        repaired_name = unidecode(original_name)
        repaired_name = re.sub(r'[\<\>\:\"\|\?\*\0]', '_', repaired_name)
        if len(repaired_name) > 200:
            repaired_name = file_path.stem[:195] + file_path.suffix
        if repaired_name != original_name:
            new_path = file_path.with_name(repaired_name)
            try:
                file_path.rename(new_path)
                self.repair_log.append(f"✓ Renamed: {original_name} → {repaired_name}")
                return new_path
            except Exception as e:
                self.repair_log.append(f"✗ Rename error: {e}")
        return file_path

    def reencode_flac(self, input_path: Path) -> Path | None:
        output_path = input_path.with_stem(f"{input_path.stem}_repaired")
        if shutil.which('flac'):
            cmd = ['flac', '--best', '--verify', '--force', '-o', str(output_path), str(input_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0:
                self.repair_log.append(f"✓ Re-encoded (flac): {output_path.name}")
                self._copy_metadata(input_path, output_path)
                return output_path
            self.repair_log.append(f"✗ Re-encode failed (flac): {result.stderr.strip()}")
        if shutil.which('ffmpeg'):
            self.repair_log.append("→ Attempting with ffmpeg...")
            cmd = ['ffmpeg', '-i', str(input_path), '-acodec', 'flac', '-y', str(output_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0:
                self.repair_log.append(f"✓ Re-encoded (ffmpeg): {output_path.name}")
                return output_path
            self.repair_log.append(f"✗ Re-encode failed (ffmpeg): {result.stderr.strip()}")
        self.repair_log.append("✗ No functional re-encoding tool (flac, ffmpeg) found.")
        return None

    def _copy_metadata(self, source: Path, dest: Path):
        try:
            original = FLAC(source); repaired = FLAC(dest)
            repaired.clear(); repaired.update(original); repaired.save()
            self.repair_log.append("  ✓ Copied metadata.")
        except Exception as e:
            self.repair_log.append(f"  ⚠ Failed to copy metadata: {e}")

class Reporter:
    @staticmethod
    def print_analysis_result(result: Dict[str, Any]):
        print(f"\n{'='*70}\nFile: {result['file']}\n{'='*70}")
        
        status_symbol = '✓' if 'VALID' in result['status'] else '✗'
        print(f"Status: {status_symbol} {result['status']}")

        if result['info']:
            print("\n--- Audio Information ---")
            for key, value in result['info'].items():
                print(f"  - {key.replace('_', ' ').title()}: {value}")
        
        if result['header_analysis'].get('metadata_blocks'):
            print("\n--- Metadata Block Structure (Low-Level) ---")
            for i, block in enumerate(result['header_analysis']['metadata_blocks']):
                print(f"  - Block {i}: Type={block['type']}, Size={block['length']}B, IsLast={block['is_last']}")
        
        if result['data_structure_analysis']:
            print("\n--- Data Structure Analysis ---")
            dsa = result['data_structure_analysis']
            print(f"  - Audio Data Start Offset: {dsa['data_start_offset']}")
            print(f"  - Expected Uncompressed Size: {dsa['expected_uncompressed_size']}")
            print(f"  - Actual Compressed Size: {dsa['actual_compressed_size']}")
            if isinstance(dsa.get('expected_uncompressed_size'), int) and isinstance(dsa.get('actual_compressed_size'), int) and dsa['actual_compressed_size'] > 0:
                ratio = dsa['actual_compressed_size'] / dsa['expected_uncompressed_size'] * 100
                print(f"  - Compression Ratio: {ratio:.2f}%")

        if result['errors']:
            print("\n--- Detected Errors ---")
            for error in result['errors']:
                print(f"  - {error}")
        
        if result['warnings']:
            print("\n--- Detected Warnings ---")
            for warning in result['warnings']:
                print(f"  - {warning}")
        
        if result['repair_suggestions']:
            print("\n--- Repair Suggestions ---")
            for sug in result['repair_suggestions']:
                print(f"  - Action: {sug['action']:<10} | Reason: {sug['reason']}")

    @staticmethod
    def print_summary(results: List[Dict[str, Any]]):
        total = len(results)
        valid_count = sum(1 for r in results if r['status'] == 'VALID')
        warn_count = sum(1 for r in results if r['status'] == 'VALID (with warnings)')
        invalid_count = total - valid_count - warn_count
        print(f"\n{'='*70}\nFINAL SUMMARY\n{'='*70}")
        print(f"Total files scanned: {total}")
        print(f"✓ Valid files: {valid_count}")
        print(f"✓ Valid files (with warnings): {warn_count}")
        print(f"✗ Invalid files: {invalid_count}")
        print(f"{'='*70}")

def find_flac_files(target_paths: List[Path]) -> Iterator[Path]:
    for path in target_paths:
        if not path.exists():
            print(f"Warning: Path '{path}' does not exist.", file=sys.stderr)
            continue
        if path.is_file() and path.suffix.lower() == '.flac':
            yield path
        elif path.is_dir():
            yield from path.rglob('*.flac')

def analyze_mode(target_paths: List[Path]):
    print("ANALYZE Mode - In-depth analysis\n" + "=" * 50)
    toolkit = FLACToolkit()
    results = [toolkit.analyze_flac_comprehensive(f) for f in find_flac_files(target_paths)]
    if not results:
        print("No FLAC files found.")
        return
    for r in results:
        Reporter.print_analysis_result(r)
    Reporter.print_summary(results)

def auto_mode(target_paths: List[Path]):
    print("AUTO Mode - Intelligent repair\n" + "=" * 50)
    toolkit = FLACToolkit()
    files_to_process = list(find_flac_files(target_paths))
    if not files_to_process:
        print("No FLAC files found.")
        return
    for file_path in files_to_process:
        print(f"\n--- Processing: {file_path} ---")
        analysis = toolkit.analyze_flac_comprehensive(file_path)
        if not analysis['repair_suggestions']:
            print("  -> No repair needed.")
            continue
        current_path = file_path
        for suggestion in analysis['repair_suggestions']:
            action = suggestion['action']
            print(f"  -> Action required: {action} ({suggestion['reason']})")
            if action == 'rename':
                current_path = toolkit.repair_filename(current_path)
            elif action == 'reencode':
                new_path = toolkit.reencode_flac(current_path)
                if new_path: current_path = new_path
    if toolkit.repair_log:
        print("\n" + "=" * 60 + "\nREPAIR REPORT\n" + "=" * 60)
        for log in toolkit.repair_log:
            print(f"  {log}")

def repair_mode(target_paths: List[Path]):
    print("REPAIR Mode - Force re-encode\n" + "=" * 50)
    toolkit = FLACToolkit()
    files_to_repair = list(find_flac_files(target_paths))
    if not files_to_repair:
        print("No FLAC files found.")
        return
    for file_path in files_to_repair:
        print(f"\n--- Repairing: {file_path} ---")
        toolkit.reencode_flac(file_path)
    if toolkit.repair_log:
        print("\n" + "=" * 60 + "\nREPAIR REPORT\n" + "=" * 60)
        for log in toolkit.repair_log:
            print(f"  {log}")

def main():
    parser = argparse.ArgumentParser(description="FLAC Toolkit (Final Version) - Advanced diagnosis and repair.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("mode", choices=['analyze', 'auto', 'repair'], help=
        "  analyze  - Perform an in-depth analysis of each file (recommended).\n"
        "  auto     - Intelligently repair files based on detected issues.\n"
        "  repair   - Force re-encoding for all target files."
    )
    parser.add_argument("target_paths", type=Path, nargs='+', help="One or more files or directories to process.")
    args = parser.parse_args()
    mode_functions = {'analyze': analyze_mode, 'auto': auto_mode, 'repair': repair_mode}
    mode_functions[args.mode](args.target_paths)

if __name__ == "__main__":
    main()