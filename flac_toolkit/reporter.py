from typing import List, Dict, Any


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
