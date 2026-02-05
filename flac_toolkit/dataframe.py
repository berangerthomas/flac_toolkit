import logging
import json
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

def create_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Generates a pandas DataFrame from a list of analysis results.
    Data is kept clean (no HTML) for Tabulator.js virtualization.
    """
    data = []
    for res in results:
        path_obj = Path(res['file'])
        
        status_order_map = {'INVALID': 0, 'VALID (with warnings)': 1, 'VALID': 2}
        
        row = {
            'file': path_obj.name,
            'file_path': str(path_obj),
            'folder': path_obj.parent.name,
            'folder_path': str(path_obj.parent),
            'status': res['status'],
            'status_order': status_order_map.get(res['status'], 99),
            'errors': '\n'.join(res['errors']),
            'warnings': '\n'.join(res['warnings']),
        }
        
        # Add metrics
        if 'metrics' in res:
            metrics = res['metrics'].copy()
            # Format duration to MM:SS
            if 'duration_seconds' in metrics:
                d_sec = metrics['duration_seconds']
                metrics['duration'] = f"{int(d_sec // 60):02d}:{int(d_sec % 60):02d}"
                del metrics['duration_seconds']
            row.update(metrics)
            
        # Add tags
        if 'tags' in res:
            row.update(res['tags'])
            
        data.append(row)
        
    df = pd.DataFrame(data)
    return df

def generate_html_report(df: pd.DataFrame, output_path: Path):
    """
    Generates a high-performance HTML report using Tabulator.js with virtual DOM.
    Handles 100,000+ rows efficiently by only rendering visible rows.
    """
    if df.empty:
        logging.warning("DataFrame is empty, cannot generate HTML report.")
        return

    # Convert DataFrame to JSON for Tabulator
    # Replace NaN with empty strings for JSON serialization
    df_clean = df.fillna('')
    data_json = df_clean.to_json(orient='records', force_ascii=False)
    
    # Calculate summary stats
    total_files = len(df)
    total_size_gb = df['filesize_mb'].sum() / 1024 if 'filesize_mb' in df.columns else 0
    invalid_count = len(df[df['status'] == 'INVALID'])
    warning_count = len(df[df['status'] == 'VALID (with warnings)'])
    valid_count = len(df[df['status'] == 'VALID'])

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>FLAC Analysis Report</title>
    <link href="https://unpkg.com/tabulator-tables@5.5.2/dist/css/tabulator_simple.min.css" rel="stylesheet">
    <script type="text/javascript" src="https://unpkg.com/tabulator-tables@5.5.2/dist/js/tabulator.min.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        html, body {{ 
            height: 100%; 
            margin: 0; 
            padding: 0;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            font-size: 13px; 
            background-color: #fff; 
            color: #333;
        }}
        
        body {{ 
            display: flex; 
            flex-direction: column; 
            padding: 20px; 
        }}
        
        h1 {{ 
            flex: 0 0 auto;
            font-size: 18px; 
            margin: 0 0 15px 0; 
            color: #2c3e50; 
            font-weight: 600;
        }}
        
        /* Summary Bar */
        .summary {{ 
            flex: 0 0 auto;
            display: flex; 
            gap: 25px; 
            padding: 12px 20px; 
            background: #f8f9fa; 
            border: 1px solid #e9ecef;
            border-radius: 6px; 
            margin-bottom: 15px;
            font-size: 13px;
            align-items: center;
        }}
        .summary-item {{ color: #666; }}
        .summary-item strong {{ color: #333; font-weight: 600; }}
        .stat-valid {{ color: #0ca678; }}
        .stat-warning {{ color: #f59f00; }}
        .stat-invalid {{ color: #fa5252; }}
        
        /* Search bar */
        .controls {{
            flex: 0 0 auto;
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            align-items: center;
        }}
        .search-box {{
            padding: 8px 12px;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            background: #fff;
            color: #333;
            font-size: 13px;
            width: 300px;
        }}
        .search-box::placeholder {{ color: #999; }}
        .search-box:focus {{ outline: none; border-color: #228be6; }}
        
        .filter-btn {{
            padding: 8px 14px;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            background: #fff;
            color: #666;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.15s;
        }}
        .filter-btn:hover {{ background: #f8f9fa; color: #333; border-color: #adb5bd; }}
        .filter-btn.active {{ background: #228be6; color: #fff; border-color: #228be6; }}
        
        /* Table container */
        #table-container {{
            flex: 1 1 auto;
            min-height: 0;
        }}
        
        /* Tabulator overrides for light theme */
        .tabulator {{
            background-color: #fff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            font-size: 13px;
        }}
        .tabulator-header {{
            background-color: #f8f9fa;
            border-bottom: 2px solid #dee2e6;
        }}
        .tabulator-header .tabulator-col {{
            background-color: #f8f9fa;
            border-right: 1px solid #e9ecef;
        }}
        .tabulator-header .tabulator-col-content {{
            padding: 10px 12px;
        }}
        .tabulator-header .tabulator-col-title {{
            font-weight: 600;
            color: #495057;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .tabulator-tableholder {{
            background: #fff;
        }}
        .tabulator-row {{
            border-bottom: 1px solid #f1f3f5;
        }}
        .tabulator-row:hover {{
            background-color: #f8f9fa !important;
        }}
        .tabulator-row.tabulator-row-even {{
            background-color: #fff;
        }}
        .tabulator-row.tabulator-row-odd {{
            background-color: #fcfcfc;
        }}
        .tabulator-cell {{
            padding: 8px 12px;
            border-right: none;
        }}
        
        /* Status badges - original style */
        .status-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            white-space: nowrap;
        }}
        .status-valid {{ background-color: #e6fcf5; color: #0ca678; border: 1px solid #c3fae8; }}
        .status-invalid {{ background-color: #fff5f5; color: #fa5252; border: 1px solid #ffc9c9; }}
        .status-warning {{ background-color: #fff9db; color: #f59f00; border: 1px solid #ffec99; }}
        
        /* Copy button */
        .copy-btn {{
            background: none;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            cursor: pointer;
            padding: 2px 6px;
            font-size: 12px;
            color: #666;
            margin-right: 6px;
            transition: all 0.15s;
        }}
        .copy-btn:hover {{ background: #f1f3f5; color: #333; }}
        
        /* Cell styles */
        .cell-errors {{ color: #e03131; white-space: pre-wrap; font-size: 12px; }}
        .cell-warnings {{ color: #e67700; white-space: pre-wrap; font-size: 12px; }}
        .cell-file {{ display: flex; align-items: center; }}
        
        /* Toast notification */
        .toast {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #333;
            color: #fff;
            padding: 12px 24px;
            border-radius: 6px;
            opacity: 0;
            transition: opacity 0.3s;
            z-index: 1000;
            font-size: 13px;
        }}
        .toast.show {{ opacity: 1; }}
    </style>
</head>
<body>
    <h1>FLAC Analysis Report</h1>
    
    <div class="summary">
        <div class="summary-item"><strong>Total Files:</strong> {total_files:,}</div>
        <div class="summary-item"><strong>Total Size:</strong> {total_size_gb:.2f} GB</div>
        <div class="summary-item stat-valid"><strong>Valid:</strong> {valid_count:,}</div>
        <div class="summary-item stat-warning"><strong>Warnings:</strong> {warning_count:,}</div>
        <div class="summary-item stat-invalid"><strong>Invalid:</strong> {invalid_count:,}</div>
    </div>
    
    <div class="controls">
        <input type="text" id="search-input" class="search-box" placeholder="Filter records...">
        <button class="filter-btn active" data-filter="all">All</button>
        <button class="filter-btn" data-filter="INVALID">Invalid</button>
        <button class="filter-btn" data-filter="VALID (with warnings)">Warnings</button>
        <button class="filter-btn" data-filter="VALID">Valid</button>
    </div>

    <div id="table-container"></div>
    <div id="toast" class="toast">Path copied!</div>

    <script>
    const tableData = {data_json};
    
    function showToast(msg) {{
        const toast = document.getElementById('toast');
        toast.textContent = msg;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2000);
    }}
    
    function copyToClipboard(text) {{
        navigator.clipboard.writeText(text).then(() => showToast('Path copied!'));
    }}
    
    // Status formatter with badge
    function statusFormatter(cell) {{
        const value = cell.getValue();
        if (value === 'VALID') {{
            return '<span class="status-badge status-valid">Valid</span>';
        }} else if (value === 'INVALID') {{
            return '<span class="status-badge status-invalid">Invalid</span>';
        }} else {{
            return '<span class="status-badge status-warning">Warning</span>';
        }}
    }}
    
    // File cell with copy button
    function fileFormatter(cell) {{
        const row = cell.getRow().getData();
        const fullPath = row.file_path || '';
        return `<div class="cell-file"><button class="copy-btn" onclick="copyToClipboard('${{fullPath.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'")}}')" title="Copy path">📋</button>${{cell.getValue()}}</div>`;
    }}
    
    // Folder cell with copy button  
    function folderFormatter(cell) {{
        const row = cell.getRow().getData();
        const folderPath = row.folder_path || '';
        return `<div class="cell-file"><button class="copy-btn" onclick="copyToClipboard('${{folderPath.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'")}}')" title="Copy path">📋</button>${{cell.getValue()}}</div>`;
    }}

    // Initialize Tabulator with virtual DOM
    const table = new Tabulator("#table-container", {{
        data: tableData,
        height: "100%",
        layout: "fitDataStretch",
        virtualDom: true,
        virtualDomBuffer: 300,
        placeholder: "No matching records found",
        initialSort: [{{ column: "status_order", dir: "asc" }}],
        columns: [
            {{ title: "File", field: "file", formatter: fileFormatter, minWidth: 250, headerFilter: false }},
            {{ title: "Folder", field: "folder", formatter: folderFormatter, minWidth: 150 }},
            {{ title: "Status", field: "status", formatter: statusFormatter, width: 110, hozAlign: "center" }},
            {{ title: "", field: "status_order", visible: false }},
            {{ title: "Errors", field: "errors", formatter: "html", cssClass: "cell-errors", minWidth: 300, formatter: function(cell) {{
                return '<div class="cell-errors">' + (cell.getValue() || '').replace(/\\n/g, '<br>') + '</div>';
            }} }},
            {{ title: "Warnings", field: "warnings", minWidth: 250, formatter: function(cell) {{
                return '<div class="cell-warnings">' + (cell.getValue() || '').replace(/\\n/g, '<br>') + '</div>';
            }} }},
            {{ title: "Duration", field: "duration", width: 90, hozAlign: "center" }},
            {{ title: "Sample Rate", field: "sample_rate", width: 110, hozAlign: "right" }},
            {{ title: "Bits", field: "bits_per_sample", width: 70, hozAlign: "center" }},
            {{ title: "Ch", field: "channels", width: 50, hozAlign: "center" }},
            {{ title: "Bitrate", field: "bitrate_kbps", width: 90, hozAlign: "right", formatter: function(cell) {{
                return cell.getValue() ? cell.getValue() + ' kbps' : '';
            }} }},
            {{ title: "Size (MB)", field: "filesize_mb", width: 100, hozAlign: "right" }},
            {{ title: "Artist", field: "artist", minWidth: 150 }},
            {{ title: "Album", field: "album", minWidth: 150 }},
            {{ title: "Title", field: "title", minWidth: 200 }},
            {{ title: "Track", field: "tracknumber", width: 70, hozAlign: "center" }},
            {{ title: "Genre", field: "genre", width: 120 }},
            {{ title: "Date", field: "date", width: 80 }},
            {{ title: "RG Gain", field: "replaygain_track_gain", width: 100 }},
        ],
    }});

    // Global search
    document.getElementById('search-input').addEventListener('input', function(e) {{
        const value = e.target.value.toLowerCase();
        table.setFilter(function(data) {{
            return Object.values(data).some(v => 
                String(v).toLowerCase().includes(value)
            );
        }});
    }});
    
    // Status filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {{
        btn.addEventListener('click', function() {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const filter = this.dataset.filter;
            if (filter === 'all') {{
                table.clearFilter();
            }} else {{
                table.setFilter("status", "=", filter);
            }}
        }});
    }});
    </script>
</body>
</html>"""
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logging.info(f"HTML report generated: {output_path}")
    except Exception as e:
        logging.error(f"Failed to write HTML report: {e}")
