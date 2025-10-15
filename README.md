# FLAC Toolkit

A command-line tool for the analysis and repair of FLAC audio files. This tool is designed to identify issues from simple metadata inconsistencies to low-level structural corruption.

## Key Features

*   **Comprehensive Analysis:** Uses both `mutagen` library and manual header parsing to detect FLAC file issues.
*   **Structural Analysis:** Detects common corruption indicators like oversized PADDING blocks.
*   **Data Structure Check:** Identifies data inconsistencies that may indicate file corruption.
*   **Repair Suggestions:** Provides repair recommendations based on detected issues.
*   **Status Classification:** Classifies files as `VALID`, `VALID (with warnings)`, or `INVALID`.
*   **Compatibility Checks:** Specifically checks for audio parameters (sample rate, bit depth, channel count) that can cause issues on Android devices.
*   **Fallback Mechanism:** Uses `flac` for repairs when available, and automatically falls back to `ffmpeg` if `flac` is not found.

## Prerequisites

*   Python 3.12+
*   Required Python packages: `mutagen`, `unidecode`
*   **Optional but Recommended:** `flac` command-line tool and/or `ffmpeg` installed and available in your system's PATH for repair functionality.

## Installation

1.  Clone the repository or download `main.py`.
2.  Install the required Python packages using uv:
    ```bash
    uv sync
    ```
3.  Ensure `flac` and/or `ffmpeg` are installed if you intend to use the `auto` or `repair` modes.

## Usage

The script is run from the command line with the following structure:

```bash
python main.py [mode] [target_paths]...
```

### Modes

*   `analyze`: Performs a detailed analysis of target files and displays a report for each.
*   `auto`: Repairs files based on analysis results. Only applies repairs to files that need them.
*   `repair`: Re-encodes all target files. Useful for standardizing an entire music library.

### Examples

*   **Analyze a single file:**
    ```bash
    python main.py analyze path/to/my_song.flac
    ```
*   **Analyze all FLAC files in a directory (recursive):**
    ```bash
    python main.py analyze path/to/my_music/
    ```
*   **Automatically repair all problematic files in a directory:**
    ```bash
    python main.py auto path/to/my_library/
    ```
*   **Force re-encoding on a selection of files:**
    ```bash
    python main.py repair file1.flac another_file.flac
    ```

## Understanding the `analyze` Output

The analysis report for each file includes the following sections:

*   **Status:** Overall file validity assessment.
*   **Audio Information:** Basic metadata like duration, sample rate, and channels.
*   **Metadata Block Structure:** Technical view of the file's internal metadata structure.
*   **Data Structure Analysis:** Information about audio data location and size.
*   **Detected Errors / Warnings:** List of identified problems.
*   **Repair Suggestions:** Recommended actions to fix detected issues.
