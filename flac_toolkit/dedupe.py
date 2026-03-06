"""
flac_toolkit/dedupe.py
Duplicate detection helpers used by validate --check-duplicates.
"""

import hashlib
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, NamedTuple


class DuplicateGroup(NamedTuple):
    audio_md5: str
    files: List[Path]
    strict_groups: List[List[Path]]  # subsets that are byte-for-byte identical


def get_file_content_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of a file (used to identify strict duplicates)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def build_duplicate_groups(audio_md5_map: Dict[str, List[Path]]) -> List[DuplicateGroup]:
    """
    Build DuplicateGroup list from a pre-computed {audio_md5: [paths]} mapping.

    Only groups with two or more files are kept. Within each group, a secondary
    SHA-256 pass identifies files that are byte-for-byte identical (strict duplicates).

    This is called by validate --check-duplicates, which passes the md5_calculated
    values already computed during RFC 9639 validation -- no extra audio I/O required.
    """
    groups = []
    for audio_md5, file_group in audio_md5_map.items():
        if len(file_group) < 2:
            continue
        content_map: Dict[str, List[Path]] = defaultdict(list)
        for f in file_group:
            content_map[get_file_content_hash(f)].append(f)
        strict_groups = [g for g in content_map.values() if len(g) > 1]
        groups.append(DuplicateGroup(
            audio_md5=audio_md5,
            files=file_group,
            strict_groups=strict_groups,
        ))
    return groups
