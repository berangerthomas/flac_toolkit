# Changelog

All notable changes to this project will be documented in this file.

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
