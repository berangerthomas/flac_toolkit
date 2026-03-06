# Changelog

## [1.0.0] - 2026-03-05

### Added

- **Machine-readable JSON data export**: Every `validate` run now also produces a `.json` file alongside the HTML report. This file contains all per-file analysis results and duplicate group data, and can be consumed by external tools or used to regenerate the HTML report without re-scanning.
- **`report` command**: New CLI command that regenerates an HTML report from a previously saved `.json` data file. Usage: `python main.py report data.json [-o output.html]`. No re-scan required — useful for refreshing reports after template updates or sharing results.
- **RFC 9639 Compliance Tests**: New test suite (`tests/test_validator_rfc9639.py`) for validating RFC 9639 compliance
- **`--check-duplicates` option for `validate` mode**: Detects audio duplicates in the same pass as validation. Because audio MD5 checksums are already computed during RFC 9639 validation, duplicate detection requires **zero additional I/O**. Strict duplicates (byte-for-byte identical files) are identified with a secondary SHA-256 pass applied only to the candidate groups. Results are exposed in a new **Duplicates tab** in the validation HTML report.
- **Duplicates tab in the validation HTML report**: When `--check-duplicates` is used, the report gains a second tab showing all duplicate groups (audio-only and strict), with sorting, filtering, copy-to-clipboard, and folder-open buttons. The tab is populated lazily on first view for zero-cost startup.
- **HTML Report popup**: Three copy formats - Text, JSON, and Markdown for structured export

### Improved

- **HTML Report popup**: Complete redesign with compact layout
  - Removed duplicate information (Sample Rate, Channels, Bits Per Sample now shown once)
  - Added new fields: Audio Quality label (CD Quality, Hi-Res 96kHz, Hi-Res 192kHz), Block Size Strategy (Fixed/Variable), Audio Offset, Audio Size
  - MD5 verification section now shows match status with color coding (green=match, red=mismatch)
  - Tags section redesigned with inline compact display
  - Metadata blocks table simplified (Type, Size, Offset)
  - Modal width reduced from 900px to 750px for better screen fit
  - All sections use 4-column grid layout for compactness

### Changed

- **PI-10 Removed**: The 16 MiB size limit check for PICTURE blocks has been removed (RFC §8.8 does not define any size limit)
- **tqdm removed**: replaced by rich.

### Removed

- **`dedupe` command**: Removed. Duplicate detection is now exclusively available via `validate --check-duplicates`, which reuses the audio MD5 already computed during RFC 9639 validation (zero extra I/O). The `--check-duplicates` path also uses the *calculated* MD5 (more reliable than the header-stored value used by the former `dedupe` command), and integrates results directly into the validation HTML report.
- **`--detailed`/`-d` option**: Removed from `validate` command. The HTML report popup is now more comprehensive than the console output ever was, making this option redundant. Users get full details by clicking the "Report" button in the HTML report.

### Technical

- **First-frame-only validation**: `_validate_frames()` rewritten to parse only the first audio frame header instead of traversing every frame. CRC-8 is still verified on the first frame; full audio integrity is guaranteed by the MD5 checksum in STREAMINFO.
- **Removed `analyze` command**: Deprecated CLI alias removed. Only `validate` is supported.

## [0.4.0] - 2026-02-20

### Added

- `--detailed`/`-d` option to the analyze command to enable detailed per-file output in the console. By default, the console output no longer lists all files to avoid excessive output as before.
- `--no-backup` option to the repair command to delete original files instead of quarantining them. Useful for large libraries where disk space is a concern (avoids doubling storage requirements).

### Changed

- **Analyze command**: Default HTML report filename is now based on the analyzed directory name (e.g., `flac_analysis_report_musique.html` instead of always `flac_analysis_report.html`). This prevents reports from overwriting each other when analyzing different directories.

### Improved

- **Repair mode**: Better visibility for skipped files. Files that are valid and don't need repair now show `Skipping (valid): <filename>` instead of being silently ignored (was previously only visible in debug mode).

### Fixed

- Re-encoding now uses short temporary filenames to avoid Windows MAX_PATH (260 chars) limit with long filenames

### Technical

- **Startup performance**: Migrated all heavy imports (`mutagen`, `tqdm`, `pandas`, `flac_toolkit.*`, `concurrent.futures`) to lazy imports inside each command function. `--help` and argument parsing now execute instantly without loading any processing dependencies.

## [0.3.0] - 2026-02-05

### Changed

- **HTML Report Engine**: Migrated from DataTables to Tabulator.js with virtual DOM rendering
  - Reports now load instantly regardless of file count (tested with 21,000+ files)
  - Only visible rows are rendered, enabling smooth scrolling through massive datasets

### Improved

- **Analyze HTML report**: Added quick filter buttons (All / Invalid / Warnings / Valid)

## [0.2.1] - 2026-01-14

### Added

- **Dedupe mode**: `-w`/`--workers` option for parallel processing

### Improved

- **Dedupe HTML report**: Visual grouping with distinct colors per duplicate group
- **Dedupe HTML report**: Added "Group" column to easily identify duplicate sets

## [0.2.0] - 2026-01-13

### Added

- **Dedupe mode**: New command to detect duplicate FLAC files in your library
  - Audio-based duplicate detection using FLAC MD5 audio signatures
  - Automatic MD5 calculation for files with missing signatures
  - Strict duplicate detection (byte-for-byte identical files) using SHA256
  - **Interactive HTML report** (`flac_duplicate_report.html`) with sorting and filtering
  - Console summary distinguishing "strict duplicates" from "audio-only duplicates"
  - `-o`/`--output` option for custom report path

### Improved

- Clearer error messages when `libsndfile` fails to read files (corruption, truncation)

## [0.1.0] - 2026-01-13

### Added

- **Analyze mode**: Comprehensive FLAC file analysis using both `mutagen` library and manual header parsing
  - Structural analysis detecting corruption indicators (oversized PADDING blocks, etc.)
  - Data structure checks for file corruption detection
  - Universal filename validation with detailed failure reasons
  - Status classification: `VALID`, `VALID (with warnings)`, or `INVALID`
- **Interactive HTML reporting**: Sortable, filterable reports with copy-to-clipboard functionality
- **Repair mode**: Automated re-encoding of structurally invalid files
  - Quarantine system moving original files to `_flac_toolkit_quarantine` folder
  - Seamless replacement preserving original filenames
  - Fallback to `ffmpeg` when `flac` CLI is unavailable
  - `--force` option to re-encode all files regardless of status
- **ReplayGain mode**: Track and album ReplayGain tag calculation based on EBU R 128 standard (-18 LUFS)
  - `--assume-album` option for treating files as a single album
- **Parallel processing**: Multi-worker support via `-w`/`--workers` option
- **Logging options**: `-v`/`--verbose` for debug output, `-q`/`--quiet` for error-only output
- **Custom output path**: `-o`/`--output` option for HTML report location

### Technical

- Python 3.12+ requirement
- Automatic versioning via `setuptools-scm`
- GitHub Actions workflow for releases