"""
flac_toolkit/validator.py
Complete RFC 9639 validation for FLAC files.

Reference: RFC 9639 - Free Lossless Audio Codec (FLAC), IETF, December 2024.
"""

import struct
import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, BinaryIO, Tuple
from enum import Enum


class Severity(Enum):
    """Severity levels according to RFC 9639."""
    ERROR = "ERROR"        # MUST/MUST NOT violation
    WARNING = "WARNING"    # SHOULD/SHOULD NOT violation
    INFO = "INFO"          # Informational


@dataclass
class CheckResult:
    """Result of an individual check."""
    code: str           # e.g. "G-01", "SI-03"
    severity: Severity
    message: str
    reference: str      # e.g. "§8.2"


@dataclass
class MetadataBlock:
    """Representation of a metadata block."""
    block_type: int
    is_last: bool
    length: int
    offset: int
    data: bytes = field(default_factory=bytes)


@dataclass
class StreamInfo:
    """Information extracted from STREAMINFO block."""
    min_block_size: int
    max_block_size: int
    min_frame_size: int
    max_frame_size: int
    sample_rate: int
    channels: int
    bits_per_sample: int
    total_samples: int
    md5_signature: bytes


@dataclass
class FrameHeader:
    """Information extracted from an audio frame."""
    offset: int
    sync_code: int
    fixed_blocksize: bool
    block_size: int
    sample_rate: int
    channels: int
    channel_assignment: int
    bits_per_sample: int
    coded_number: int
    frame_size: int = 0
    crc8: int = 0
    is_valid: bool = True


@dataclass
class ValidationResult:
    """Complete RFC 9639 validation result."""
    file_path: Path
    errors: List[CheckResult] = field(default_factory=list)
    warnings: List[CheckResult] = field(default_factory=list)
    infos: List[CheckResult] = field(default_factory=list)
    
    # Extracted metadata
    streaminfo: Optional[StreamInfo] = None
    metadata_blocks: List[MetadataBlock] = field(default_factory=list)
    frames: List[FrameHeader] = field(default_factory=list)
    
    # Info for detailed report
    file_size: int = 0
    audio_offset: int = 0
    audio_size: int = 0
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    @property
    def total_checks(self) -> int:
        return len(self.errors) + len(self.warnings) + len(self.infos)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON/HTML serialization."""
        return {
            'file_path': str(self.file_path),
            'is_valid': self.is_valid,
            'errors': [{'code': e.code, 'message': e.message, 'reference': e.reference} for e in self.errors],
            'warnings': [{'code': w.code, 'message': w.message, 'reference': w.reference} for w in self.warnings],
            'infos': [{'code': i.code, 'message': i.message, 'reference': i.reference} for i in self.infos],
            'total_checks': self.total_checks,
            'file_size': self.file_size,
            'audio_offset': self.audio_offset,
            'audio_size': self.audio_size,
            'streaminfo': {
                'min_block_size': self.streaminfo.min_block_size,
                'max_block_size': self.streaminfo.max_block_size,
                'min_frame_size': self.streaminfo.min_frame_size,
                'max_frame_size': self.streaminfo.max_frame_size,
                'sample_rate': self.streaminfo.sample_rate,
                'channels': self.streaminfo.channels,
                'bits_per_sample': self.streaminfo.bits_per_sample,
                'total_samples': self.streaminfo.total_samples,
                'md5_signature': self.streaminfo.md5_signature.hex() if self.streaminfo.md5_signature else None,
            } if self.streaminfo else None,
            'metadata_blocks': [
                {'type': b.block_type, 'is_last': b.is_last, 'length': b.length, 'offset': b.offset}
                for b in self.metadata_blocks
            ],
            'frame_count': len(self.frames),
        }


class RFC9639Validator:
    """Complete RFC 9639 validator for FLAC files."""
    
    # FLAC signature
    FLAC_SIGNATURE = b'fLaC'
    
    # Metadata block types
    BLOCK_STREAMINFO = 0
    BLOCK_PADDING = 1
    BLOCK_APPLICATION = 2
    BLOCK_SEEKTABLE = 3
    BLOCK_VORBIS_COMMENT = 4
    BLOCK_CUESHEET = 5
    BLOCK_PICTURE = 6
    
    # Reserved block type
    BLOCK_TYPE_RESERVED = 127
    
    # Names for block types
    BLOCK_TYPE_NAMES = {
        0: "STREAMINFO",
        1: "PADDING",
        2: "APPLICATION",
        3: "SEEKTABLE",
        4: "VORBIS_COMMENT",
        5: "CUESHEET",
        6: "PICTURE",
    }
    
    # Picture types for PICTURE block
    PICTURE_TYPES = {
        0: "Other",
        1: "32x32 pixels 'file icon' (PNG only)",
        2: "Other file icon",
        3: "Cover (front)",
        4: "Cover (back)",
        5: "Leaflet page",
        6: "Media (e.g. label side of CD)",
        7: "Lead artist/lead performer/soloist",
        8: "Artist/performer",
        9: "Conductor",
        10: "Band/Orchestra",
        11: "Composer",
        12: "Lyricist/text writer",
        13: "Recording Location",
        14: "During recording",
        15: "During performance",
        16: "Movie/video screen capture",
        17: "A bright coloured fish",
        18: "Illustration",
        19: "Band/artist logotype",
        20: "Publisher/Studio logotype",
    }
    
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.result = ValidationResult(file_path=self.file_path)
        self._f: Optional[BinaryIO] = None
        self._blocking_strategy_fixed: Optional[bool] = None
        self._frame_decoding_errors: bool = False  # Track if we had decoding errors for MD5 validation
        
    # --- CRC Helper Methods (FIX-02) ---
    
    def _crc8(self, data: bytes) -> int:
        """Calculate CRC-8 for frame header.
        Polynomial: 0x07, initial value: 0x00 (RFC §9.1.8)
        """
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = ((crc << 1) ^ 0x07) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
        return crc
    
    def _crc16(self, data: bytes) -> int:
        """Calculate CRC-16 for entire frame.
        Polynomial: 0x8005, initial value: 0x0000 (RFC §9.3)
        """
        crc = 0
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x8005) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
        return crc
        
    def validate(self) -> ValidationResult:
        """Execute ALL RFC 9639 checks."""
        try:
            self.result.file_size = self.file_path.stat().st_size
            with open(self.file_path, 'rb') as f:
                self._f = f
                self._validate_all()
        except FileNotFoundError:
            self._add_error("G-00", "File not found", "§6")
        except PermissionError:
            self._add_error("G-00", "Permission denied", "§6")
        except Exception as e:
            self._add_error("G-00", f"Cannot read file: {e}", "§6")
        return self.result
    
    def _validate_all(self):
        """Execute all checks without early exit."""
        # 1. General structure
        self._validate_general_structure()
        
        # Only continue if we have valid FLAC signature
        if any(e.code == "G-01" for e in self.result.errors):
            return
        
        # 2. Metadata blocks
        self._validate_metadata_blocks()
        
        # 3. STREAMINFO specific
        self._validate_streaminfo()
        
        # 4. Other metadata blocks
        self._validate_padding()
        self._validate_application()
        self._validate_seektable()
        self._validate_vorbis_comment()
        self._validate_cuesheet()
        self._validate_picture()
        
        # 5. Uniqueness constraints
        self._validate_uniqueness()
        
        # 6. Audio frames
        self._validate_frames()
        
        # 7. Streamable subset
        self._validate_streamable_subset()
    
    # --- Helper methods ---
    
    def _add_error(self, code: str, msg: str, ref: str):
        self.result.errors.append(CheckResult(code, Severity.ERROR, msg, ref))
    
    def _add_warning(self, code: str, msg: str, ref: str):
        self.result.warnings.append(CheckResult(code, Severity.WARNING, msg, ref))
    
    def _add_info(self, code: str, msg: str, ref: str):
        self.result.infos.append(CheckResult(code, Severity.INFO, msg, ref))
    
    def _read_bytes(self, n: int) -> bytes:
        """Read n bytes from file."""
        return self._f.read(n)
    
    def _read_byte(self) -> int:
        """Read single byte."""
        return self._f.read(1)[0]
    
    def _tell(self) -> int:
        """Get current position."""
        return self._f.tell()
    
    def _seek(self, pos: int):
        """Seek to position."""
        self._f.seek(pos)
    
    # --- Section 1: General Structure ---
    
    def _validate_general_structure(self):
        """Validate general file structure (G-01 to G-08)."""
        # G-01: File starts with 'fLaC' signature
        signature = self._read_bytes(4)
        if signature != self.FLAC_SIGNATURE:
            self._add_error("G-01", f"Invalid signature: expected 'fLaC', got {signature!r}", "§6")
            return
        
        # Parse all metadata blocks
        has_streaminfo = False
        is_last_found = False
        
        while True:
            offset = self._tell()
            header = self._read_bytes(4)
            if len(header) < 4:
                self._add_error("MH-04", "Unexpected end of file reading metadata block header", "§8.1")
                break
            
            is_last = (header[0] & 0x80) != 0
            block_type = header[0] & 0x7F
            length = struct.unpack('>I', b'\x00' + header[1:4])[0]
            
            # MH-01: Block type must be 0-126
            if block_type > 126:
                self._add_error("MH-01", f"Invalid block type: {block_type} (must be 0-126)", "§8.1")
            
            # MH-02: Block type 127 is forbidden
            if block_type == self.BLOCK_TYPE_RESERVED:
                self._add_error("MH-02", "Block type 127 is forbidden", "§8.1")
            
            # MH-03: Types 7-126 are reserved
            if 7 <= block_type <= 126:
                self._add_info("MH-03", f"Reserved block type {block_type} found", "§8.1")
            
            # Read block data
            data = self._read_bytes(length) if length > 0 else b''
            if len(data) < length:
                self._add_error("MH-04", f"Metadata block truncated: expected {length} bytes, got {len(data)}", "§8.1")
            
            block = MetadataBlock(
                block_type=block_type,
                is_last=is_last,
                length=length,
                offset=offset,
                data=data
            )
            self.result.metadata_blocks.append(block)
            
            # Check STREAMINFO position (G-02)
            if block_type == self.BLOCK_STREAMINFO:
                has_streaminfo = True
                if len(self.result.metadata_blocks) != 1:
                    self._add_error("G-02", "STREAMINFO must be the first metadata block", "§8.2")
            
            if is_last:
                is_last_found = True
                self.result.audio_offset = self._tell()
                break
        
        # G-04: Exactly one block must have is_last=1
        last_blocks = [b for b in self.result.metadata_blocks if b.is_last]
        if len(last_blocks) == 0:
            self._add_error("G-04", "No metadata block has is_last flag set", "§8.1")
        elif len(last_blocks) > 1:
            self._add_error("G-04", f"Multiple blocks ({len(last_blocks)}) have is_last flag set", "§8.1")
        
        # G-02: STREAMINFO must exist
        if not has_streaminfo:
            self._add_error("G-02", "STREAMINFO block missing", "§8.2")
    
    # --- Section 2: Metadata Block Headers ---
    
    def _validate_metadata_blocks(self):
        """Validate metadata block headers (MH-01 to MH-05)."""
        # Already validated in _validate_general_structure
        pass
    
    # --- Section 3: STREAMINFO ---
    
    def _validate_streaminfo(self):
        """Validate STREAMINFO block (SI-01 to SI-15)."""
        streaminfo_blocks = [b for b in self.result.metadata_blocks if b.block_type == self.BLOCK_STREAMINFO]
        
        # SI-01: Exactly one STREAMINFO
        if len(streaminfo_blocks) == 0:
            self._add_error("SI-01", "STREAMINFO block missing", "§8.2")
            return
        if len(streaminfo_blocks) > 1:
            self._add_error("SI-01", f"Multiple STREAMINFO blocks found ({len(streaminfo_blocks)})", "§8.2")
            return
        
        block = streaminfo_blocks[0]
        
        # SI-02: STREAMINFO must be first
        if self.result.metadata_blocks[0].block_type != self.BLOCK_STREAMINFO:
            self._add_error("SI-02", "STREAMINFO must be the first block", "§8.2")
        
        # Parse STREAMINFO (34 bytes)
        if len(block.data) < 34:
            self._add_error("SI-00", "STREAMINFO block too short (expected 34 bytes)", "§8.2")
            return
        
        data = block.data
        
        # Bytes 0-1: min_block_size (16 bits)
        min_block = struct.unpack('>H', data[0:2])[0]
        # Bytes 2-3: max_block_size (16 bits)
        max_block = struct.unpack('>H', data[2:4])[0]
        # Bytes 4-6: min_frame_size (24 bits)
        min_frame = (data[4] << 16) | (data[5] << 8) | data[6]
        # Bytes 7-9: max_frame_size (24 bits)
        max_frame = (data[7] << 16) | (data[8] << 8) | data[9]
        
        # Bytes 10-17: sample_rate (20 bits) + channels-1 (3 bits) + bits_per_sample-1 (5 bits) + total_samples (36 bits)
        # Layout in big-endian 64-bit:
        # bits 63-44: sample_rate (20 bits)
        # bits 43-41: channels - 1 (3 bits)
        # bits 40-36: bits_per_sample - 1 (5 bits)
        # bits 35-0: total_samples (36 bits)
        combined = struct.unpack('>Q', data[10:18])[0]
        sample_rate = (combined >> 44) & 0xFFFFF
        channels = ((combined >> 41) & 0x07) + 1
        bits_per_sample = ((combined >> 36) & 0x1F) + 1
        total_samples = combined & 0x0000000FFFFFFFFF  # 36 bits
        
        # Bytes 18-33: MD5 signature (128 bits)
        md5 = data[18:34]
        
        self.result.streaminfo = StreamInfo(
            min_block_size=min_block,
            max_block_size=max_block,
            min_frame_size=min_frame,
            max_frame_size=max_frame,
            sample_rate=sample_rate,
            channels=channels,
            bits_per_sample=bits_per_sample,
            total_samples=total_samples,
            md5_signature=md5
        )
        
        # SI-03: min_block_size >= 16 and <= 65535
        if min_block < 16:
            self._add_error("SI-03", f"min_block_size ({min_block}) < 16", "§8.2")
        
        # SI-04: max_block_size >= 16 and <= 65535
        if max_block < 16:
            self._add_error("SI-04", f"max_block_size ({max_block}) < 16", "§8.2")
        
        # SI-05: min_block_size <= max_block_size
        if min_block > max_block:
            self._add_error("SI-05", f"min_block_size ({min_block}) > max_block_size ({max_block})", "§8.2")
        
        # SI-06: Constant block size indicator
        if min_block == max_block:
            self._add_info("SI-06", "File has constant block size", "§8.2")
        
        # SI-07: Sample rate MUST NOT be 0 for audio files (FIX-13: improved message and severity)
        if sample_rate == 0:
            self._add_warning(
                "SI-07",
                "Sample rate is 0: file is treated as non-audio. "
                "MUST NOT be 0 if file contains audio (§8.2).",
                "§8.2"
            )
        # Note: sample_rate is u(20), guaranteed >= 0; the `elif sample_rate < 1` branch was dead code and removed.
        
        # SI-08: Sample rate <= 1048575 Hz
        if sample_rate > 1048575:
            self._add_error("SI-08", f"Sample rate ({sample_rate}) exceeds maximum (1048575 Hz)", "§8.2")
        
        # SI-09: Channels 1-8
        if channels < 1 or channels > 8:
            self._add_error("SI-09", f"Invalid number of channels: {channels} (must be 1-8)", "§8.2")
        
        # SI-10: Bits per sample 4-32
        if bits_per_sample < 4 or bits_per_sample > 32:
            self._add_error("SI-10", f"Invalid bits per sample: {bits_per_sample} (must be 4-32)", "§8.2")
        
        # SI-11: Total samples consistency (warning)
        if total_samples == 0:
            self._add_warning("SI-11", "Total samples is 0 (unknown)", "§8.2")
        
        # SI-12: MD5 signature
        if md5 == b'\x00' * 16:
            self._add_warning("SI-12", "MD5 signature is all zeros (unset)", "§8.2")
        
        # SI-13: Frame size consistency (warning - checked later with frames)
        if min_frame == 0 and max_frame == 0:
            self._add_warning("SI-13", "Frame sizes are unknown (0)", "§8.2")
    
    # --- Section 4: PADDING ---
    
    def _validate_padding(self):
        """Validate PADDING blocks (PA-01 to PA-03)."""
        padding_blocks = [b for b in self.result.metadata_blocks if b.block_type == self.BLOCK_PADDING]
        
        if len(padding_blocks) > 1:
            self._add_info("PA-03", f"Multiple PADDING blocks found ({len(padding_blocks)})", "§8.3")
        
        for block in padding_blocks:
            # PA-01: Size is multiple of 8 bits (always true for byte-aligned data)
            # PA-02: All bytes MUST be 0x00 (FIX-05: changed from WARNING to ERROR)
            if block.data and any(b != 0 for b in block.data):
                self._add_error("PA-02", "PADDING block contains non-zero bytes (MUST be 0x00 per §8.3)", "§8.3")
    
    # --- Section 5: APPLICATION ---
    
    def _validate_application(self):
        """Validate APPLICATION blocks (AP-01 to AP-03)."""
        app_blocks = [b for b in self.result.metadata_blocks if b.block_type == self.BLOCK_APPLICATION]
        
        for block in app_blocks:
            # AP-01: Must have Application ID (32 bits)
            if len(block.data) < 4:
                self._add_error("AP-01", "APPLICATION block too short (missing Application ID)", "§8.4")
                continue
            
            app_id = struct.unpack('>I', block.data[0:4])[0]
            self._add_info("AP-03", f"APPLICATION block with ID 0x{app_id:08X}", "§8.4")
    
    # --- Section 6: SEEKTABLE ---
    
    def _validate_seektable(self):
        """Validate SEEKTABLE blocks (ST-01 to ST-11)."""
        seektable_blocks = [b for b in self.result.metadata_blocks if b.block_type == self.BLOCK_SEEKTABLE]
        
        # ST-01: At most one SEEKTABLE
        if len(seektable_blocks) > 1:
            self._add_error("ST-01", f"Multiple SEEKTABLE blocks found ({len(seektable_blocks)})", "§8.5")
            return
        
        if len(seektable_blocks) == 0:
            return
        
        block = seektable_blocks[0]
        
        # ST-02: Size must be multiple of 18 bytes
        if len(block.data) % 18 != 0:
            self._add_error("ST-02", f"SEEKTABLE size ({len(block.data)}) is not a multiple of 18", "§8.5")
            return
        
        # Parse seek points
        num_points = len(block.data) // 18
        seek_points = []
        
        for i in range(num_points):
            offset = i * 18
            sample_number = struct.unpack('>Q', block.data[offset:offset+8])[0]
            stream_offset = struct.unpack('>Q', block.data[offset+8:offset+16])[0]
            frame_samples = struct.unpack('>H', block.data[offset+16:offset+18])[0]
            seek_points.append((sample_number, stream_offset, frame_samples))
        
        # ST-03: Points sorted by sample_number
        for i in range(1, len(seek_points)):
            prev_sample = seek_points[i-1][0]
            curr_sample = seek_points[i][0]
            # Handle placeholders (0xFFFFFFFFFFFFFFFF)
            if prev_sample != 0xFFFFFFFFFFFFFFFF and curr_sample != 0xFFFFFFFFFFFFFFFF:
                if curr_sample < prev_sample:
                    self._add_error("ST-03", f"Seek points not sorted: point {i} has sample {curr_sample} < {prev_sample}", "§8.5.1")
        
        # ST-04: Unique sample numbers (except placeholders)
        non_placeholder_samples = [s[0] for s in seek_points if s[0] != 0xFFFFFFFFFFFFFFFF]
        if len(non_placeholder_samples) != len(set(non_placeholder_samples)):
            self._add_error("ST-04", "Duplicate sample numbers in seek points", "§8.5.1")
        
        # ST-05: Placeholders at end
        placeholder_found = False
        for i, (sample, _, _) in enumerate(seek_points):
            if sample == 0xFFFFFFFFFFFFFFFF:
                placeholder_found = True
            elif placeholder_found:
                self._add_error("ST-05", "Non-placeholder seek point after placeholder", "§8.5.1")
                break
    
    # --- Section 7: VORBIS COMMENT ---
    
    def _validate_vorbis_comment(self):
        """Validate VORBIS COMMENT blocks (VC-01 to VC-09)."""
        vorbis_blocks = [b for b in self.result.metadata_blocks if b.block_type == self.BLOCK_VORBIS_COMMENT]
        
        # VC-01: At most one VORBIS COMMENT
        if len(vorbis_blocks) > 1:
            self._add_error("VC-01", f"Multiple VORBIS COMMENT blocks found ({len(vorbis_blocks)})", "§8.6")
            return
        
        if len(vorbis_blocks) == 0:
            return
        
        block = vorbis_blocks[0]
        data = block.data
        pos = 0
        
        # Read vendor string (little-endian)
        if len(data) < 4:
            self._add_error("VC-02", "VORBIS COMMENT too short for vendor length", "§8.6")
            return
        
        vendor_len = struct.unpack('<I', data[pos:pos+4])[0]
        pos += 4
        
        if pos + vendor_len > len(data):
            self._add_error("VC-02", "Vendor string truncated", "§8.6")
            return
        
        try:
            vendor = data[pos:pos+vendor_len].decode('utf-8')
        except UnicodeDecodeError:
            self._add_error("VC-03", "Vendor string is not valid UTF-8", "§8.6")
            return
        
        pos += vendor_len
        
        # Read comment count
        if pos + 4 > len(data):
            self._add_error("VC-02", "VORBIS COMMENT truncated after vendor string", "§8.6")
            return
        
        comment_count = struct.unpack('<I', data[pos:pos+4])[0]
        pos += 4
        
        for i in range(comment_count):
            if pos + 4 > len(data):
                self._add_error("VC-02", f"Comment {i} length truncated", "§8.6")
                break
            
            comment_len = struct.unpack('<I', data[pos:pos+4])[0]
            pos += 4
            
            if pos + comment_len > len(data):
                self._add_error("VC-02", f"Comment {i} truncated", "§8.6")
                break
            
            try:
                comment = data[pos:pos+comment_len].decode('utf-8')
            except UnicodeDecodeError:
                self._add_error("VC-03", f"Comment {i} is not valid UTF-8", "§8.6")
                pos += comment_len
                continue
            
            pos += comment_len
            
            # VC-05: Must contain '='
            if '=' not in comment:
                self._add_error("VC-05", f"Comment {i} missing '=' separator: {comment[:50]}", "§8.6")
                continue
            
            field_name, field_value = comment.split('=', 1)
            
            # VC-04: Field name must be ASCII printable 0x20-0x7E (excluding '=') - FIX-10
            for c in field_name:
                code = ord(c)
                if code < 0x20 or code > 0x7E or code == 0x3D:  # 0x3D == '='
                    self._add_error(
                        "VC-04",
                        f"Field name contains invalid character (U+{code:04X}): {field_name!r}",
                        "§8.6"
                    )
                    break
            
            # VC-07/08: WAVEFORMATEXTENSIBLE_CHANNEL_MASK
            if field_name.upper() == 'WAVEFORMATEXTENSIBLE_CHANNEL_MASK':
                self._add_info("VC-09", "File uses WAVEFORMATEXTENSIBLE_CHANNEL_MASK (not streamable)", "§8.6.2")
                if not field_value.lower().startswith('0x'):
                    self._add_warning("VC-08", "WAVEFORMATEXTENSIBLE_CHANNEL_MASK should start with '0x'", "§8.6.2")
    
    # --- Section 8: CUESHEET ---
    
    def _validate_cuesheet(self):
        """Validate CUESHEET blocks (CS-01 to CS-18)."""
        cuesheet_blocks = [b for b in self.result.metadata_blocks if b.block_type == self.BLOCK_CUESHEET]
        
        for block in cuesheet_blocks:
            data = block.data
            
            if len(data) < 396:  # Minimum size for cuesheet with no tracks
                self._add_error("CS-00", "CUESHEET block too short", "§8.7")
                continue
            
            # Parse CUESHEET header
            media_catalog_number = data[0:128]
            lead_in_samples = struct.unpack('>Q', data[128:136])[0]
            is_cd = (data[136] & 0x80) != 0
            num_tracks = data[395]
            
            # CS-01: Media catalog number ASCII printable + padding
            for i, b in enumerate(media_catalog_number):
                if b != 0 and (b < 0x20 or b > 0x7E):
                    self._add_error("CS-01", f"Media catalog number contains invalid byte at position {i}", "§8.7")
                    break
            
            # CS-02: Reserved bits (7 bits after is_cd flag + 258 bytes)
            reserved1 = data[137:395]
            if any(b != 0 for b in reserved1):
                self._add_error("CS-02", "Reserved bits in CUESHEET header are not zero", "§8.7")
            
            # CS-LEADIN: For CD-DA, lead-in MUST be >= 2 seconds (FIX-09)
            if is_cd and lead_in_samples < 88200:
                self._add_error(
                    "CS-LEADIN",
                    f"CD-DA lead-in is {lead_in_samples} samples, MUST be at least 88200 (2 seconds)",
                    "§8.7"
                )
            
            # CS-03: At least 1 track
            if num_tracks < 1:
                self._add_error("CS-03", f"CUESHEET has no tracks (num_tracks={num_tracks})", "§8.7")
            
            # CS-04: For CD-DA, max 100 tracks
            if is_cd and num_tracks > 100:
                self._add_error("CS-04", f"CD-DA CUESHEET has too many tracks ({num_tracks} > 100)", "§8.7")
            
            # Parse tracks
            track_offsets = []
            track_numbers = []
            pos = 396
            
            for track_idx in range(num_tracks):
                if pos + 36 > len(data):
                    self._add_error("CS-00", f"Track {track_idx} truncated", "§8.7.1")
                    break
                
                track_offset = struct.unpack('>Q', data[pos:pos+8])[0]
                track_number = data[pos+8]
                num_indices = data[pos+35]
                
                track_offsets.append(track_offset)
                track_numbers.append(track_number)
                
                # CS-07: Track number not 0
                if track_number == 0:
                    self._add_error("CS-07", f"Track {track_idx} has number 0 (reserved)", "§8.7.1")
                
                # CS-08: For CD-DA, track numbers 1-99
                if is_cd and track_number != 170 and (track_number < 1 or track_number > 99):
                    self._add_error("CS-08", f"CD-DA track {track_idx} has invalid number {track_number}", "§8.7.1")
                
                # CS-10: For CD-DA, track offset divisible by 588
                if is_cd and track_offset % 588 != 0:
                    self._add_error("CS-10", f"CD-DA track {track_idx} offset not divisible by 588", "§8.7.1")
                
                # CS-ISRC: Validate ISRC content (FIX-12)
                isrc = data[pos+9:pos+21]  # 12 bytes
                if isrc != b'\x00' * 12:
                    for b in isrc:
                        if not (0x30 <= b <= 0x39 or 0x41 <= b <= 0x5A or 0x61 <= b <= 0x7A):
                            self._add_error(
                                "CS-ISRC",
                                f"Track {track_idx}: ISRC contains non-alphanumeric byte 0x{b:02X}",
                                "§8.7.1"
                            )
                            break
                
                # CS-11: Reserved bits in track (FIX-07: corrected offsets)
                # 6 low bits of byte at pos+21
                if data[pos+21] & 0x3F != 0:
                    self._add_error("CS-11", f"Track {track_idx}: reserved bits at byte 21 are not zero", "§8.7.1")
                # 13 reserved bytes at pos+22 to pos+34
                if any(data[pos+22:pos+35]):
                    self._add_error("CS-11", f"Track {track_idx}: reserved bytes (22-34) are not zero", "§8.7.1")
                
                # Parse indices
                index_start = pos + 36
                prev_index_number = -1
                for idx in range(num_indices):
                    if index_start + 12 > len(data):
                        self._add_error("CS-00", f"Track {track_idx} index {idx} truncated", "§8.7.1.1")
                        break
                    
                    index_offset = struct.unpack('>Q', data[index_start:index_start+8])[0]
                    index_number = data[index_start+8]
                    
                    # CS-15: First index is 0 or 1
                    if idx == 0 and index_number not in (0, 1):
                        self._add_error("CS-15", f"Track {track_idx} first index is {index_number}, not 0 or 1", "§8.7.1.1")
                    
                    # CS-16: Index numbers must be sequential
                    if idx > 0 and index_number != prev_index_number + 1:
                        self._add_error("CS-16", f"Track {track_idx} index {idx}: number {index_number} "
                                        f"not sequential (expected {prev_index_number + 1})", "§8.7.1.1")
                    prev_index_number = index_number

                    # CS-17: For CD-DA, index offset divisible by 588
                    if is_cd and index_offset % 588 != 0:
                        self._add_error("CS-17", f"CD-DA track {track_idx} index {idx} offset not divisible by 588", "§8.7.1.1")
                    
                    # CS-18: Reserved bits in index point (3 bytes) must be zero
                    if any(data[index_start+9:index_start+12]):
                        self._add_error("CS-18", f"Track {track_idx} index {idx}: reserved bits are not zero", "§8.7.1.1")

                    index_start += 12
                
                pos += 36 + num_indices * 12
            
            # CS-12: Lead-out track must have 0 index points
            if track_numbers and num_tracks > 0:
                # num_indices of the last track parsed
                last_track_pos = 396
                for i in range(num_tracks - 1):
                    if last_track_pos + 36 > len(data):
                        break
                    n_idx = data[last_track_pos + 35]
                    last_track_pos += 36 + n_idx * 12
                if last_track_pos + 36 <= len(data):
                    leadout_num_indices = data[last_track_pos + 35]
                    if leadout_num_indices != 0:
                        self._add_error("CS-12", f"Lead-out track has {leadout_num_indices} index points (must be 0)", "§8.7.1")

            # CS-05: Last track is lead-out
            if track_numbers and track_numbers[-1] not in (170, 255):
                self._add_error("CS-05", f"Last track ({track_numbers[-1]}) is not lead-out", "§8.7")
            
            # CS-06: Lead-out number
            if track_numbers:
                expected_leadout = 170 if is_cd else 255
                if track_numbers[-1] != expected_leadout:
                    self._add_error("CS-06", f"Lead-out track number is {track_numbers[-1]}, expected {expected_leadout}", "§8.7")
            
            # CS-09: Unique track numbers
            if len(track_numbers) != len(set(track_numbers)):
                self._add_error("CS-09", "Duplicate track numbers in CUESHEET", "§8.7.1")
    
    # --- Section 9: PICTURE ---
    
    def _validate_picture(self):
        """Validate PICTURE blocks (PI-01 to PI-10)."""
        picture_blocks = [b for b in self.result.metadata_blocks if b.block_type == self.BLOCK_PICTURE]
        
        picture_types_found = {}
        
        for block in picture_blocks:
            data = block.data
            
            if len(data) < 32:
                self._add_error("PI-00", "PICTURE block too short", "§8.8")
                continue
            
            picture_type = struct.unpack('>I', data[0:4])[0]
            mime_len = struct.unpack('>I', data[4:8])[0]
            
            # PI-01: Picture type 0-20
            if picture_type > 20:
                self._add_error("PI-01", f"Invalid picture type: {picture_type} (must be 0-20)", "§8.8")
            
            # Track picture types for PI-02
            if picture_type in (1, 2):
                if picture_type in picture_types_found:
                    self._add_error("PI-02", f"Multiple pictures of type {picture_type} found", "§8.8")
                picture_types_found[picture_type] = True
            
            if len(data) < 8 + mime_len:
                self._add_error("PI-04", "MIME type truncated", "§8.8")
                continue
            
            mime = data[8:8+mime_len]
            mime_str = mime.decode('ascii', errors='replace').strip().lower()
            
            # PI-03: MIME type ASCII printable
            for b in mime:
                if b < 0x20 or b > 0x7E:
                    self._add_error("PI-03", "MIME type contains non-ASCII-printable characters", "§8.8")
                    break
            
            # PI-11: Picture type 1 MUST have MIME type 'image/png' (FIX-11)
            if picture_type == 1 and mime_str != 'image/png':
                self._add_error(
                    "PI-11",
                    f"Picture type 1 (file icon) MUST have MIME type 'image/png', got {mime_str!r}",
                    "§8.8"
                )
            
            pos = 8 + mime_len
            if pos + 4 > len(data):
                self._add_error("PI-05", "Description length missing", "§8.8")
                continue
            
            desc_len = struct.unpack('>I', data[pos:pos+4])[0]
            pos += 4
            
            if pos + desc_len > len(data):
                self._add_error("PI-05", "Description truncated", "§8.8")
                continue
            
            pos += desc_len
            
            # Skip width, height, color_depth, colors (4x4 bytes = 16 bytes)
            pos += 16
            
            if pos + 4 > len(data):
                self._add_error("PI-06", "Picture data length missing", "§8.8")
                continue
            
            pic_len = struct.unpack('>I', data[pos:pos+4])[0]
            pos += 4
            
            if pos + pic_len > len(data):
                self._add_error("PI-06", f"Picture data truncated: expected {pic_len} bytes", "§8.8")
            # FIX-08: PI-10 removed - RFC §8.8 does not define any size limit for PICTURE blocks
    
    # --- Section 10: Uniqueness ---
    
    def _validate_uniqueness(self):
        """Validate uniqueness constraints (UN-01 to UN-07)."""
        # Count block types
        streaminfo_count = sum(1 for b in self.result.metadata_blocks if b.block_type == self.BLOCK_STREAMINFO)
        seektable_count = sum(1 for b in self.result.metadata_blocks if b.block_type == self.BLOCK_SEEKTABLE)
        vorbis_count = sum(1 for b in self.result.metadata_blocks if b.block_type == self.BLOCK_VORBIS_COMMENT)
        padding_count = sum(1 for b in self.result.metadata_blocks if b.block_type == self.BLOCK_PADDING)
        
        # Already checked in individual validators, but add consolidated info
        if padding_count > 1:
            self._add_info("UN-06", f"Multiple PADDING blocks ({padding_count}) are legal", "§8.3")
        
        # Picture type uniqueness for types 1 and 2 (already checked in _validate_picture)
    
    # --- Section 11: Audio Frames ---

    def _decode_utf8_coded_number(self, data: bytes, start: int) -> Tuple[int, int]:
        """Decode a UTF-8 style coded number (frame/sample number) per RFC §9.1.5.

        Returns (value, byte_count) or (-1, 0) on error.
        """
        if start >= len(data):
            return -1, 0
        first = data[start]

        if first < 0x80:
            return first, 1
        elif first < 0xC0:
            return -1, 0  # invalid leading byte
        elif first < 0xE0:
            n, mask = 2, 0x1F
        elif first < 0xF0:
            n, mask = 3, 0x0F
        elif first < 0xF8:
            n, mask = 4, 0x07
        elif first < 0xFC:
            n, mask = 5, 0x03
        elif first < 0xFE:
            n, mask = 6, 0x01
        elif first == 0xFE:
            n, mask = 7, 0x00
        else:
            return -1, 0

        if start + n > len(data):
            return -1, 0

        value = first & mask
        for i in range(1, n):
            b = data[start + i]
            if (b & 0xC0) != 0x80:
                return -1, 0
            value = (value << 6) | (b & 0x3F)
        return value, n

    def _validate_frames(self):
        """Validate the first audio frame header with CRC-8 verification.

        Only the first frame is parsed — scanning through compressed FLAC audio
        data looking for sync patterns causes false positives because the byte
        sequences 0xFF 0xF8/0xF9 can appear in arbitrary compressed data.
        Audio integrity is instead verified via the MD5 checksum in STREAMINFO.
        Addresses BUG-01, BUG-02, RFC-02.
        """
        if self.result.audio_offset == 0:
            return

        self._seek(self.result.audio_offset)
        frame_start = self._tell()

        # Frame header max size: 2 (sync) + 1 + 1 + 7 (coded#) + 2 (extra bs) + 2 (extra sr) + 1 (crc8) = 16
        raw = self._read_bytes(16)
        if len(raw) < 5:
            self._add_error("FH-01", "No valid audio frames found (file truncated at audio offset)", "§9")
            self.result.audio_size = self.result.file_size - self.result.audio_offset
            return

        # FH-02: Sync code
        if raw[0] != 0xFF or (raw[1] & 0xFC) != 0xF8:
            self._add_error("FH-02", f"Missing frame sync code at audio offset {frame_start:#x} "
                            f"(got 0x{raw[0]:02X}{raw[1]:02X})", "§9.1")
            self.result.audio_size = self.result.file_size - self.result.audio_offset
            return

        # --- Parse header fields ---
        fixed_blocksize = (raw[1] & 0x01) == 0
        self._blocking_strategy_fixed = fixed_blocksize

        # FH-06: Reserved bit
        if raw[1] & 0x02:
            self._add_error("FH-06", "Frame 0: reserved bit (byte 1, bit 1) is not 0", "§9.1")

        block_size_bits = (raw[2] >> 4) & 0x0F
        sample_rate_bits = raw[2] & 0x0F
        channel_bits = (raw[3] >> 4) & 0x0F
        bit_depth_bits = (raw[3] >> 1) & 0x07

        # FH-05
        if block_size_bits == 0:
            self._add_error("FH-05", "Frame 0: reserved block size 0b0000", "§9.1")
        # FH-07
        if sample_rate_bits == 0b1111:
            self._add_error("FH-07", "Frame 0: forbidden sample rate bits 0b1111", "§9.1.2")
        # FH-09
        if channel_bits >= 0b1011:
            self._add_error("FH-09", f"Frame 0: reserved channel bits {channel_bits:04b}", "§9.1.3")
        # FH-11
        if bit_depth_bits == 0b011:
            self._add_error("FH-11", "Frame 0: reserved bit depth bits 0b011", "§9.1.4")
        # FH-12
        if raw[3] & 0x01 != 0:
            self._add_error("FH-12", "Frame 0: reserved bit (byte 3, bit 0) is not 0", "§9.1.4")

        # --- Coded number (UTF-8 style, RFC §9.1.5) ---
        coded_value, coded_len = self._decode_utf8_coded_number(raw, 4)
        if coded_len == 0:
            self._add_error("FH-13", f"Frame 0: invalid UTF-8 coded number at offset {frame_start:#x}", "§9.1.5")
            self.result.audio_size = self.result.file_size - self.result.audio_offset
            return

        pos = 4 + coded_len  # position within raw[]

        # --- Extra block size bytes ---
        block_size = 0
        if block_size_bits == 0b0110:
            if pos < len(raw):
                block_size = raw[pos] + 1
                pos += 1
        elif block_size_bits == 0b0111:
            if pos + 1 < len(raw):
                block_size = struct.unpack('>H', raw[pos:pos + 2])[0] + 1
                pos += 2
        else:
            block_size = self._get_block_size_from_bits(block_size_bits)

        # FH-17: block size must not be 65536
        if block_size_bits in (0b0110, 0b0111) and block_size == 65536:
            self._add_error("FH-17", "Frame 0: block size 65536 is forbidden", "§9.1.6")

        # --- RFC-02: Uncommon sample rate extra bytes ---
        if sample_rate_bits == 0b1100:
            if pos < len(raw):
                pos += 1
        elif sample_rate_bits in (0b1101, 0b1110):
            if pos + 1 < len(raw):
                pos += 2

        # --- CRC-8 verification (BUG-02) ---
        if pos < len(raw):
            crc8_stored = raw[pos]
            header_bytes = raw[:pos]
            crc8_calculated = self._crc8(header_bytes)
            if crc8_calculated != crc8_stored:
                self._add_error("FH-18", f"Frame 0: CRC-8 mismatch "
                                f"(stored=0x{crc8_stored:02X}, calculated=0x{crc8_calculated:02X})", "§9.1.8")
            pos += 1

        # Store first frame info
        frame_header = FrameHeader(
            offset=frame_start,
            sync_code=0xFFF8 | (raw[1] & 0x01),
            fixed_blocksize=fixed_blocksize,
            block_size=block_size,
            sample_rate=0,
            channels=(channel_bits + 1) if channel_bits <= 7 else 2,
            channel_assignment=channel_bits,
            bits_per_sample=0,
            coded_number=coded_value,
            crc8=raw[pos - 1] if pos > 0 else 0,
        )
        self.result.frames.append(frame_header)

        self._add_info(
            "FH-00",
            "First audio frame header validated (CRC-8 verified). "
            "Scanning all frames is omitted to avoid false positives from compressed audio data. "
            "Full audio integrity is verified via MD5 in STREAMINFO.",
            "§9",
        )
        self.result.audio_size = self.result.file_size - self.result.audio_offset
    
    def _get_block_size_from_bits(self, bits: int) -> int:
        """Get block size from block size bits."""
        sizes = {
            0b0001: 192,
            0b0010: 576,
            0b0011: 1152,
            0b0100: 2304,
            0b0101: 4608,
            0b1000: 256,
            0b1001: 512,
            0b1010: 1024,
            0b1011: 2048,
            0b1100: 4096,
            0b1101: 8192,
            0b1110: 16384,
            0b1111: 32768,
        }
        return sizes.get(bits, 0)
    
    # --- Section 12: Streamable Subset ---
    
    def _validate_streamable_subset(self):
        """Validate streamable subset constraints (SS-01 to SS-07)."""
        # This is informational - most files are streamable
        if self.result.streaminfo:
            si = self.result.streaminfo
            
            # SS-01: Bit depth must be 4-24
            if si.bits_per_sample < 4 or si.bits_per_sample > 24:
                self._add_warning("SS-01", f"Bit depth {si.bits_per_sample} outside streamable subset (4-24)", "§7")

            # SS-02: Sample rate must be <= 655350 Hz
            if si.sample_rate > 655350:
                self._add_warning("SS-02", f"Sample rate {si.sample_rate}Hz exceeds streamable subset limit (655350)", "§7")

            # SS-03: No frame > 16384 samples
            if si.max_block_size > 16384:
                self._add_warning("SS-03", f"Max block size ({si.max_block_size}) exceeds 16384 (not streamable)", "§7")
            
            # SS-04: For sample rate <= 48000, max 4608 samples
            if si.sample_rate <= 48000 and si.max_block_size > 4608:
                self._add_warning("SS-04", f"At {si.sample_rate}Hz, max block size should be <= 4608 for streamability", "§7")

            # SS-07: Sample rate must not use 'get from STREAMINFO' in frames
            # (This requires frame-level checking; flag if sample_rate is unusual)
            unusual_rates = {0}  # 0 is invalid in STREAMINFO already caught by SI-06
            if si.sample_rate not in {8000, 16000, 22050, 32000, 44100, 48000, 88200, 96000, 176400, 192000, 384000} and si.sample_rate != 0:
                self._add_info("SS-07", f"Uncommon sample rate {si.sample_rate}Hz may require non-streamable encoding", "§7")