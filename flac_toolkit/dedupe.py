import hashlib
import logging
import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, NamedTuple, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from mutagen.flac import FLAC
from flac_toolkit.core import find_flac_files
from flac_toolkit.analyzer import _calculate_audio_md5

class DuplicateGroup(NamedTuple):
    audio_md5: str
    files: List[Path]
    strict_groups: List[List[Path]] # subsets of files that are strictly identical

def get_file_content_hash(path: Path) -> str:
    """Calculates SHA256 of the file content."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _get_audio_signature(file_path: Path) -> Tuple[Path, Optional[str], Optional[str]]:
    """
    Worker function to get audio MD5 signature for a single file.
    Returns (file_path, signature_hex, error_message).
    """
    try:
        audio = FLAC(file_path)
        sig = audio.info.md5_signature
        
        if sig == 0:
            # If signature is missing in header, calculate it manually
            calc_sig, err = _calculate_audio_md5(file_path, audio.info.bits_per_sample)
            if calc_sig:
                return (file_path, calc_sig, None)
            else:
                return (file_path, None, err)
        else:
            return (file_path, format(sig, '032x'), None)
    except Exception as e:
        return (file_path, None, str(e))


def find_duplicates(target_paths: List[Path], workers: Optional[int] = None) -> List[DuplicateGroup]:
    """
    Finds groups of files with identical audio content.
    Within those groups, identifies files that are strictly identical (byte-for-byte).
    """
    files = list(find_flac_files(target_paths))
    if not files:
        return []

    # Map: Audio MD5 -> List of files
    audio_map = defaultdict(list)
    
    if workers is not None and workers == 1:
        # Sequential execution
        tqdm.write("Running in sequential mode (1 worker).")
        for f in tqdm(files, desc="Scanning audio signatures", unit="file", miniters=1, mininterval=0.0, file=sys.stdout):
            f, sig_hex, err = _get_audio_signature(f)
            if err:
                logging.warning(f"\nSkipping: {f}\n  Reason: {err}")
            elif sig_hex:
                audio_map[sig_hex].append(f)
    else:
        # Parallel execution
        effective_workers = workers if workers else os.cpu_count()
        # Limit workers on Windows
        if effective_workers and effective_workers > 61:
            effective_workers = 61
        tqdm.write(f"Running in parallel mode ({effective_workers} workers).")
        
        with ProcessPoolExecutor(max_workers=effective_workers) as executor:
            futures = [executor.submit(_get_audio_signature, f) for f in files]
            for future in tqdm(as_completed(futures), total=len(files), desc="Scanning audio signatures", unit="file", miniters=1, mininterval=0.0, file=sys.stdout):
                file_path, sig_hex, err = future.result()
                if err:
                    logging.warning(f"\nSkipping: {file_path}\n  Reason: {err}")
                elif sig_hex:
                    audio_map[sig_hex].append(file_path)

    results = []
    
    # Filter groups with > 1 item
    potential_duplicates = {k: v for k, v in audio_map.items() if len(v) > 1}
    
    for audio_md5, file_group in tqdm(potential_duplicates.items(), desc="Verifying duplicates content", unit="group"):
        
        # Check for strict duplicates within this audio group
        content_map = defaultdict(list)
        for f in file_group:
            h = get_file_content_hash(f)
            content_map[h].append(f)
            
        strict_groups = [g for g in content_map.values() if len(g) > 1]
        
        results.append(DuplicateGroup(
            audio_md5=audio_md5,
            files=file_group,
            strict_groups=strict_groups
        ))
        
    return results

def print_duplicate_report(results: List[DuplicateGroup]):
    if not results:
        print("\nNo duplicates found!")
        return

    print(f"\nFound {len(results)} groups of duplicate audio content.\n")
    
    for i, group in enumerate(results, 1):
        print(f"Group {i} (Audio MD5: {group.audio_md5})")
        print("-" * 60)
        
        # We need to display them intelligently.
        # If files are in a strict group, group them visually.
        
        processed_files = set()
        
        # 1. Print Strict Duplicates Groups
        if group.strict_groups:
            print("  [Strict Duplicates - Identical Files]")
            for s_group in group.strict_groups:
                print("    ├── " + str(s_group[0]))
                for f in s_group[1:]:
                    print("    ├── " + str(f))
                    processed_files.add(f)
                processed_files.add(s_group[0])
                print("    └── (End of identical set)")
                print()
        
        # 2. Print remaining files (Audio match only)
        remaining = [f for f in group.files if f not in processed_files]
        if remaining:
            label = "  [Audio Only Duplicates - Different Metadata/Name]" if group.strict_groups else "  [Audio Duplicates]"
            print(label)
            for f in remaining:
                print(f"    - {f}")
        
        print("\n")


def generate_dedupe_html_report(results: List[DuplicateGroup], output_path: Path):
    """
    Generates an interactive HTML report for duplicate detection results.
    """
    if not results:
        logging.info("No duplicates found, skipping HTML report generation.")
        return
    
    # Calculate stats
    total_groups = len(results)
    total_duplicate_files = sum(len(g.files) for g in results)
    total_strict_sets = sum(len(g.strict_groups) for g in results)
    
    # Build table rows - generate distinct colors for groups
    # Using 3 alternating colors as requested
    
    # CSS classes for alternating colors
    # Targeting both tr and td with high specificity to override DataTables styles
    group_css = """
        table.dataTable tbody tr.group-color-0,
        table.dataTable tbody tr.group-color-0 > td,
        table.dataTable tbody tr.group-color-0 > td.sorting_1 {
            background-color: #e3f2fd !important;
            box-shadow: none !important;
        }
        
        table.dataTable tbody tr.group-color-1,
        table.dataTable tbody tr.group-color-1 > td,
        table.dataTable tbody tr.group-color-1 > td.sorting_1 {
            background-color: #f1f8e9 !important;
            box-shadow: none !important;
        }
        
        table.dataTable tbody tr.group-color-2,
        table.dataTable tbody tr.group-color-2 > td,
        table.dataTable tbody tr.group-color-2 > td.sorting_1 {
            background-color: #fff3e0 !important;
            box-shadow: none !important;
        }
    """
    
    table_rows = []
    for group_idx, group in enumerate(results, 1):
        # Determine color class cyclically
        color_class = f"group-color-{group_idx % 3}"

        for f in group.files:
            # Determine duplicate type
            is_strict = any(f in sg for sg in group.strict_groups)
            dup_type = "Strict" if is_strict else "Audio-Only"
            dup_type_class = "status-invalid" if is_strict else "status-warning"
            
            # Get file info
            try:
                audio = FLAC(f)
                artist = (audio.get('artist') or [''])[0]
                album = (audio.get('album') or [''])[0]
                title = (audio.get('title') or [''])[0]
                size_mb = round(f.stat().st_size / (1024 * 1024), 2)
            except:
                artist = album = title = ""
                size_mb = 0
            
            # Escape paths for JS
            full_path_str = str(f).replace('\\', '\\\\').replace("'", "\\'")
            folder_path_str = str(f.parent).replace('\\', '\\\\').replace("'", "\\'")
            folder_uri = f.parent.as_uri()
            
            file_cell = (
                f'<div class="file-cell">'
                f'<button class="copy-btn" onclick="copyToClipboard(\'{full_path_str}\')" title="Copy full path">📋</button>'
                f'<span class="filename-text" title="{f.name}">{f.name}</span>'
                f'</div>'
            )
            
            folder_cell = (
                f'<div class="file-cell">'
                f'<button class="copy-btn" onclick="copyToClipboard(\'{folder_path_str}\')" title="Copy folder path">📋</button>'
                f'<a href="{folder_uri}" class="folder-link" title="Open folder in explorer">📂</a>'
                f'<span class="filename-text" title="{f.parent}">{f.parent.name}</span>'
                f'</div>'
            )
            
            table_rows.append(f"""
                <tr class="{color_class}" data-group="{group_idx}">
                    <td class="col-group">{group_idx}</td>
                    <td>{file_cell}</td>
                    <td>{folder_cell}</td>
                    <td><span class="status-badge {dup_type_class}">{dup_type}</span></td>
                    <td class="col-md5" title="{group.audio_md5}">{group.audio_md5[:16]}...</td>
                    <td class="col-truncated" title="{artist}">{artist}</td>
                    <td class="col-truncated" title="{album}">{album}</td>
                    <td class="col-truncated" title="{title}">{title}</td>
                    <td>{size_mb}</td>
                </tr>
            """)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FLAC Duplicate Report</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
        <script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
        <style>
            /* Dynamic group colors */
            {group_css}
            
            html, body {{ 
                height: 100%; 
                margin: 0; 
                padding: 0; 
                overflow: hidden;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
                font-size: 13px; 
                color: #333; 
                background-color: #fff; 
            }}
            
            body {{ 
                display: flex; 
                flex-direction: column; 
                padding: 20px; 
                box-sizing: border-box; 
            }}
            
            h1 {{ 
                flex: 0 0 auto;
                font-size: 18px; 
                margin: 0 0 15px 0; 
                color: #2c3e50; 
                font-weight: 600;
            }}
            
            .summary {{ 
                flex: 0 0 auto;
                display: flex; 
                gap: 25px; 
                padding: 12px 20px; 
                background: #f8f9fa; 
                border: 1px solid #e9ecef;
                border-radius: 6px; 
                margin-bottom: 20px;
                font-size: 13px;
                align-items: center;
            }}
            .summary-item {{ color: #666; }}
            .summary-item strong {{ color: #333; font-weight: 600; }}
            
            #table-container {{
                flex: 1 1 auto;
                overflow: hidden;
                display: flex;
                flex-direction: column;
            }}
            
            .dataTables_wrapper {{
                display: flex;
                flex-direction: column;
                height: 100%;
            }}
            .dataTables_filter, .dataTables_info {{ flex: 0 0 auto; padding: 5px 0; }}
            .dataTables_scroll {{ 
                flex: 1 1 auto; 
                overflow: hidden; 
                display: flex; 
                flex-direction: column;
            }}
            .dataTables_scrollHead {{ flex: 0 0 auto; }}
            .dataTables_scrollBody {{ 
                flex: 1 1 auto; 
                border-bottom: 1px solid #dee2e6;
            }}
            
            table.dataTable {{ 
                border-collapse: collapse !important; 
                width: 100% !important; 
                border: none;
            }}
            table.dataTable thead th {{ 
                background-color: #f8f9fa !important; 
                color: #495057 !important; 
                border-bottom: 2px solid #dee2e6 !important;
                font-weight: 600;
                padding: 10px 12px !important;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                white-space: nowrap;
            }}
            table.dataTable tbody td {{ 
                padding: 8px 12px !important; 
                border-bottom: 1px solid #f1f3f5;
                vertical-align: middle;
            }}
            
            /* Disable DataTables alternating row colors - let inline styles take over */
            table.dataTable tbody tr,
            table.dataTable tbody tr.odd,
            table.dataTable tbody tr.even,
            table.dataTable.display tbody tr.odd,
            table.dataTable.display tbody tr.even {{
                background-color: transparent !important;
            }}
            
            .status-badge {{
                display: inline-block;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                white-space: nowrap;
            }}
            .status-invalid {{ background-color: #fff5f5; color: #fa5252; border: 1px solid #ffc9c9; }}
            .status-warning {{ background-color: #fff9db; color: #f59f00; border: 1px solid #ffec99; }}
            
            .col-truncated {{
                max-width: 150px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .col-md5 {{
                font-family: "SFMono-Regular", Consolas, monospace;
                font-size: 11px;
                color: #868e96;
            }}
            
            .file-cell {{
                display: flex;
                align-items: center;
                gap: 8px;
                max-width: 300px;
            }}
            .filename-text {{
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                flex: 1;
            }}
            .copy-btn {{
                background: none;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                cursor: pointer;
                padding: 2px 6px;
                font-size: 12px;
                color: #666;
            }}
            .copy-btn:hover {{ background-color: #f1f3f5; }}
            .folder-link {{
                text-decoration: none;
                font-size: 14px;
            }}
            .folder-link:hover {{ opacity: 0.7; }}
            
            /* Group row coloring - distinct colors per group */
            .col-group {{
                font-weight: 600;
                text-align: center;
                color: #495057;
            }}
        </style>
    </head>
    <body>
        <h1>FLAC Duplicate Report</h1>
        
        <div class="summary">
            <div class="summary-item"><strong>Duplicate Groups:</strong> {total_groups}</div>
            <div class="summary-item"><strong>Total Duplicate Files:</strong> {total_duplicate_files}</div>
            <div class="summary-item"><strong>Strict Duplicate Sets:</strong> <span style="color:#fa5252; font-weight:bold;">{total_strict_sets}</span></div>
        </div>

        <div id="table-container">
            <table id="dedupe-table" class="display" style="width:100%">
                <thead>
                    <tr>
                        <th>Group</th>
                        <th>File</th>
                        <th>Folder</th>
                        <th>Type</th>
                        <th>Audio MD5</th>
                        <th>Artist</th>
                        <th>Album</th>
                        <th>Title</th>
                        <th>Size (MB)</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>

        <script>
        function copyToClipboard(text) {{
            navigator.clipboard.writeText(text);
        }}

        $(document).ready(function () {{
            $('#dedupe-table').DataTable({{
                paging: false,
                scrollX: true,
                scrollY: '100%',
                scrollCollapse: true,
                autoWidth: true,
                stripeClasses: [],
                orderClasses: false,
                order: [[0, 'asc'], [3, 'asc']],
                language: {{
                    search: "Filter:",
                    info: "Showing _TOTAL_ duplicate files"
                }},
                dom: 'frti'
            }});
        }});
        </script>
        
    </body>
    </html>
    """
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logging.info(f"HTML report generated: {output_path}")
    except Exception as e:
        logging.error(f"Failed to write HTML report: {e}")
