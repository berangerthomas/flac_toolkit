# Changelog

## [Unreleased] - Next version

### Added

-

### Improved

-

### Changed

-

### Fixed

-

### Technical

-

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
