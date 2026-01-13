# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
