import logging
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

def create_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Generates a pandas DataFrame from a list of analysis results.
    """
    data = []
    for res in results:
        path_obj = Path(res['file'])
        folder_uri = path_obj.parent.as_uri()
        full_path_str = str(path_obj).replace('\\', '\\\\').replace("'", "\\'") # Escape for JS
        
        filename = path_obj.name
        display_filename = filename

        # Create a copy button and truncated text
        file_cell = (
            f'<div class="file-cell">'
            f'<button class="copy-btn" onclick="copyToClipboard(\'{full_path_str}\')" title="Copy full path">📋</button>'
            f'<span class="filename-text" title="{filename}">{display_filename}</span>'
            f'</div>'
        )
        
        # Create folder cell with copy button
        folder_path_str = str(path_obj.parent).replace('\\', '\\\\').replace("'", "\\'")
        folder_cell = (
            f'<div class="file-cell">'
            f'<button class="copy-btn" onclick="copyToClipboard(\'{folder_path_str}\')" title="Copy folder path">📋</button>'
            f'<span class="filename-text" title="{path_obj.parent.name}">{path_obj.parent.name}</span>'
            f'</div>'
        )
        
        status_order_map = {'INVALID': 0, 'VALID (with warnings)': 1, 'VALID': 2}
        
        row = {
            'File': file_cell,
            'Folder': folder_cell,
            'Status': res['status'],
            'StatusOrder': status_order_map.get(res['status'], 99),
            'Errors': '<br>'.join(res['errors']),
            'Warnings': '<br>'.join(res['warnings']),
        }
        
        # Add metrics
        if 'metrics' in res:
            metrics = res['metrics'].copy()
            # Format duration to MM:SS
            if 'duration_seconds' in metrics:
                d_sec = metrics['duration_seconds']
                metrics['Duration'] = f"{int(d_sec // 60):02d}:{int(d_sec % 60):02d}"
                del metrics['duration_seconds']
            
            row.update(metrics)
            
        # Add tags
        if 'tags' in res:
            row.update(res['tags'])
            
        data.append(row)
        
    df = pd.DataFrame(data)
    
    # Ensure correct column order for JS indexing
    core_cols = ['File', 'Folder', 'Status', 'StatusOrder', 'Errors', 'Warnings']
    other_cols = [col for col in df.columns if col not in core_cols]
    df = df[core_cols + other_cols]
    
    return df

def generate_html_report(df: pd.DataFrame, output_path: Path):
    """
    Generates a styled HTML report from the DataFrame.
    """
    if df.empty:
        logging.warning("DataFrame is empty, cannot generate HTML report.")
        return

    # Professional styling with Flexbox layout for single scrollbar
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FLAC Analysis Report</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
        <script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
        <style>
            html, body {{ 
                height: 100%; 
                margin: 0; 
                padding: 0; 
                overflow: hidden; /* Prevent body scroll */
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
            
            /* Summary Bar */
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
            
            /* Table Container - Takes remaining height */
            #table-container {{
                flex: 1 1 auto;
                overflow: hidden; /* Let DataTables handle scroll */
                display: flex;
                flex-direction: column;
            }}
            
            /* DataTables Overrides for Flexbox */
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
            
            /* Table Styling */
            table.dataTable {{ 
                border-collapse: collapse !important; 
                width: 100% !important; 
                border: none;
                table-layout: auto; /* Allow dynamic sizing */
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
                position: sticky;
                top: 0;
                z-index: 10;
                white-space: nowrap;
            }}
            table.dataTable tbody td {{ 
                padding: 8px 12px !important; 
                border-bottom: 1px solid #f1f3f5;
                vertical-align: middle;
                line-height: 1.4;
            }}
            
            /* Status Badges */
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
            
            /* Columns */
            td.col-errors, td.col-warnings {{ 
                color: #495057;
                /* No fixed width, let it grow/shrink, but wrap text */
                white-space: normal;
                min-width: 300px; /* Minimum readable width */
            }}
            
            /* Truncated Columns */
            td.col-truncated {{
                max-width: 150px; /* Trigger truncation */
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                cursor: help; /* Indicate hover capability */
            }}
            
            td.col-duration {{ 
                white-space: nowrap; 
                font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            }}
            
            /* File Cell */
            .file-cell {{
                display: flex;
                align-items: center;
                gap: 8px;
                max-width: 350px;
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
            .copy-btn:hover {{ background-color: #f1f3f5; color: #333; }}
            
            a {{ color: #228be6; text-decoration: none; font-weight: 500; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <h1>FLAC Analysis Report</h1>
        
        <div class="summary">
            <div class="summary-item"><strong>Total Files:</strong> {len(df)}</div>
            <div class="summary-item"><strong>Total Size:</strong> {df['filesize_mb'].sum() / 1024:.2f} GB</div>
            <div class="summary-item"><strong>Invalid:</strong> <span style="color:#fa5252; font-weight:bold;">{len(df[df['Status'] == 'INVALID'])}</span></div>
        </div>

        <div id="table-container">
            <table id="flac-table" class="display" style="width:100%">
                <thead>
                    <tr>
                        {''.join(f'<th>{col}</th>' for col in df.columns)}
                    </tr>
                </thead>
                <tbody>
                    {_generate_table_rows(df)}
                </tbody>
            </table>
        </div>

        <script>
        function copyToClipboard(text) {{
            navigator.clipboard.writeText(text).then(function() {{
                // Optional: Show a small toast or change button color temporarily
            }}, function(err) {{
                console.error('Async: Could not copy text: ', err);
            }});
        }}

        $(document).ready( function () {{
            $('#flac-table').DataTable({{
                paging: false,
                scrollX: true,
                scrollY: '100%',
                scrollCollapse: true,
                autoWidth: true,
                // Set the default sort order to the StatusOrder column
                order: [[3, 'asc']],
                columnDefs: [
                    // Hide the StatusOrder column (index 3)
                    {{ "visible": false, "targets": 3 }},
                    // Tell the Status column (index 2) to use the StatusOrder column for sorting
                    {{ "orderData": 3, "targets": 2 }}
                ],
                language: {{
                    search: "Filter records:",
                    info: "Showing _TOTAL_ files"
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

def _generate_table_rows(df: pd.DataFrame) -> str:
    rows = []
    # Columns that should NOT be truncated
    full_cols = {'File', 'Folder', 'Status', 'Errors', 'Warnings', 'md5_header', 'md5_calculated'}
    
    for _, row in df.iterrows():
        cells = []
        for col in df.columns:
            val = row[col]
            str_val = str(val)
            
            # Apply specific classes based on column name
            cls = ""
            content = str_val
            title_attr = ""
            
            if col == 'Errors':
                cls = 'col-errors'
            elif col == 'Warnings':
                cls = 'col-warnings'
            elif col == 'Duration':
                cls = 'col-duration'
            elif col == 'Status':
                if val == 'VALID':
                    content = '<span class="status-badge status-valid">Valid</span>'
                elif val == 'INVALID':
                    content = '<span class="status-badge status-invalid">Invalid</span>'
                else:
                    content = '<span class="status-badge status-warning">Warning</span>'
            elif col not in full_cols:
                # Truncate other columns
                cls = 'col-truncated'
                title_attr = f'title="{str_val.replace('"', '&quot;')}"'
            
            cells.append(f'<td class="{cls}" {title_attr}>{content}</td>')
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return '\n'.join(rows)
