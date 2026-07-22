from pathlib import Path, PurePosixPath
import struct
import warnings
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile
import zlib

from PIL import Image, UnidentifiedImageError

from app.services.file_safety.contracts import FileSafetyError, ProcessingLimits


OLE_COMPOUND_HEADER = bytes.fromhex("D0CF11E0A1B11AE1")
OFFICE_EXTENSIONS = frozenset({".docx", ".xlsx", ".xlsm"})
UNSUPPORTED_EXTENSIONS = frozenset({".xls", ".pptx"})
IMAGE_SIGNATURES = {
    ".jpeg": b"\xff\xd8\xff",
    ".jpg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
}
EXPECTED_MIME_TYPES = {
    ".csv": frozenset({"text/csv", "application/csv", "application/vnd.ms-excel"}),
    ".docx": frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    ),
    ".jpeg": frozenset({"image/jpeg"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".pdf": frozenset({"application/pdf"}),
    ".png": frozenset({"image/png"}),
    ".txt": frozenset({"text/plain"}),
    ".webp": frozenset({"image/webp"}),
    ".xlsm": frozenset({"application/vnd.ms-excel.sheet.macroenabled.12"}),
    ".xlsx": frozenset(
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    ),
}
OFFICE_CONTENT_MARKERS = {
    ".docx": "wordprocessingml.document.main+xml",
    ".xlsx": "spreadsheetml.sheet.main+xml",
    ".xlsm": "ms-excel.sheet.macroenabled.main+xml",
}


def validate_file_for_processing(
    *,
    path: Path,
    extension: str,
    mime_type: str,
    limits: ProcessingLimits,
) -> None:
    normalized_extension = extension.lower()
    if normalized_extension in UNSUPPORTED_EXTENSIONS:
        raise FileSafetyError("file_type_unsupported", "不支持该文件类型")
    allowed_mime_types = EXPECTED_MIME_TYPES.get(normalized_extension)
    if allowed_mime_types is None:
        raise FileSafetyError("file_type_unsupported", "不支持该文件类型")
    normalized_mime = mime_type.partition(";")[0].strip().lower()
    if normalized_mime not in allowed_mime_types:
        raise FileSafetyError("file_mime_mismatch", "文件类型与声明不一致")
    try:
        byte_size = path.stat().st_size
        with path.open("rb") as file_handle:
            header = file_handle.read(16)
    except OSError as exception:
        raise FileSafetyError("file_unavailable", "文件不可读取") from exception
    if byte_size > limits.max_file_bytes:
        raise FileSafetyError("file_too_large", "文件大小超过允许上限")
    if normalized_extension in IMAGE_SIGNATURES or normalized_extension == ".webp":
        if byte_size > limits.max_image_bytes:
            raise FileSafetyError("image_too_large", "图片大小超过允许上限")
        _validate_image_signature(normalized_extension, header)
        _validate_image_structure(path, normalized_extension, byte_size)
        _decode_image(path, normalized_extension, limits.max_image_decoded_bytes)
    elif normalized_extension == ".pdf":
        if not header.startswith(b"%PDF-"):
            raise FileSafetyError("file_mime_mismatch", "文件类型与声明不一致")
    elif normalized_extension in OFFICE_EXTENSIONS:
        _validate_office_archive(path, normalized_extension, header, limits)
    else:
        _validate_text_payload(path)


def _validate_image_signature(extension: str, header: bytes) -> None:
    if extension == ".webp":
        is_valid = (
            len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
        )
    else:
        is_valid = header.startswith(IMAGE_SIGNATURES[extension])
    if not is_valid:
        raise FileSafetyError("file_mime_mismatch", "文件类型与声明不一致")


def _validate_image_structure(path: Path, extension: str, byte_size: int) -> None:
    try:
        with path.open("rb") as file_handle:
            if extension == ".png":
                _validate_png(file_handle, byte_size)
            elif extension in {".jpg", ".jpeg"}:
                _validate_jpeg(file_handle, byte_size)
            else:
                _validate_webp(file_handle, byte_size)
    except FileSafetyError:
        raise
    except (OSError, OverflowError, struct.error, ValueError, zlib.error) as exception:
        raise FileSafetyError("image_corrupt", "图片文件损坏") from exception


def _decode_image(path: Path, extension: str, max_decoded_bytes: int) -> None:
    expected_format = {
        ".jpeg": "JPEG",
        ".jpg": "JPEG",
        ".png": "PNG",
        ".webp": "WEBP",
    }[extension]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.format != expected_format:
                    raise FileSafetyError("file_mime_mismatch", "文件类型与声明不一致")
                width, height = image.size
                decoded_bytes = width * height * max(4, len(image.getbands()))
                if width <= 0 or height <= 0 or decoded_bytes > max_decoded_bytes:
                    raise FileSafetyError(
                        "image_decoded_too_large", "图片解码后超过安全上限"
                    )
                image.load()
    except FileSafetyError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as exception:
        raise FileSafetyError("image_corrupt", "图片文件损坏") from exception


def _read_exact(file_handle, byte_count: int) -> bytes:
    payload = file_handle.read(byte_count)
    if len(payload) != byte_count:
        raise FileSafetyError("image_corrupt", "图片文件损坏")
    return payload


def _validate_png(file_handle, byte_size: int) -> None:
    if _read_exact(file_handle, 8) != IMAGE_SIGNATURES[".png"]:
        raise FileSafetyError("image_corrupt", "图片文件损坏")
    saw_header = False
    saw_data = False
    saw_end = False
    ended_data = False
    consumed = 8
    decompressor = zlib.decompressobj()
    decompressed_bytes = 0
    expected_decompressed_bytes: int | None = None
    indexed_color = False
    saw_palette = False
    while consumed < byte_size:
        length, chunk_type = struct.unpack(">I4s", _read_exact(file_handle, 8))
        consumed += 8
        if length > byte_size - consumed - 4:
            raise FileSafetyError("image_corrupt", "图片文件损坏")
        checksum = zlib.crc32(chunk_type)
        remaining = length
        header_payload = bytearray()
        while remaining:
            chunk = _read_exact(file_handle, min(remaining, 64 * 1024))
            if chunk_type == b"IHDR" and len(header_payload) < 13:
                header_payload.extend(chunk[: 13 - len(header_payload)])
            if chunk_type == b"IDAT":
                pending = chunk
                while pending:
                    output = decompressor.decompress(pending, 64 * 1024)
                    decompressed_bytes += len(output)
                    if (
                        expected_decompressed_bytes is None
                        or decompressed_bytes > expected_decompressed_bytes
                    ):
                        raise FileSafetyError("image_corrupt", "图片文件损坏")
                    pending = decompressor.unconsumed_tail
            checksum = zlib.crc32(chunk, checksum)
            remaining -= len(chunk)
        expected_checksum = struct.unpack(">I", _read_exact(file_handle, 4))[0]
        consumed += length + 4
        if checksum & 0xFFFFFFFF != expected_checksum:
            raise FileSafetyError("image_corrupt", "图片文件损坏")
        if not saw_header:
            if chunk_type != b"IHDR" or length != 13:
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            width, height = struct.unpack(">II", header_payload[:8])
            bit_depth = header_payload[8]
            color_type = header_payload[9]
            interlace = header_payload[12]
            if (
                width == 0
                or height == 0
                or header_payload[10:12] != b"\x00\x00"
                or interlace not in {0, 1}
            ):
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            expected_decompressed_bytes = _png_decompressed_size(
                width, height, bit_depth, color_type, interlace
            )
            if expected_decompressed_bytes > 250 * 1024 * 1024:
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            indexed_color = color_type == 3
            saw_header = True
        elif chunk_type == b"IHDR":
            raise FileSafetyError("image_corrupt", "图片文件损坏")
        elif chunk_type == b"PLTE":
            if saw_data or length == 0 or length % 3 or length > 768:
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            saw_palette = True
        elif chunk_type == b"IDAT":
            if ended_data or (indexed_color and not saw_palette):
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            saw_data = True
        elif chunk_type == b"IEND":
            if (
                length != 0
                or consumed != byte_size
                or not decompressor.eof
                or decompressor.unused_data
                or decompressed_bytes != expected_decompressed_bytes
            ):
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            saw_end = True
            break
        elif saw_data:
            ended_data = True
    if not (saw_header and saw_data and saw_end):
        raise FileSafetyError("image_corrupt", "图片文件损坏")


def _png_decompressed_size(
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    interlace: int,
) -> int:
    allowed_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if bit_depth not in allowed_depths.get(color_type, set()):
        raise FileSafetyError("image_corrupt", "图片文件损坏")
    bits_per_pixel = channels[color_type] * bit_depth
    if interlace == 0:
        return height * (1 + ((width * bits_per_pixel + 7) // 8))
    total = 0
    for start_x, start_y, step_x, step_y in (
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    ):
        pass_width = _png_pass_extent(width, start_x, step_x)
        pass_height = _png_pass_extent(height, start_y, step_y)
        if pass_width and pass_height:
            total += pass_height * (1 + ((pass_width * bits_per_pixel + 7) // 8))
    return total


def _png_pass_extent(size: int, start: int, step: int) -> int:
    if size <= start:
        return 0
    return (size - start + step - 1) // step


def _next_jpeg_marker(file_handle) -> int:
    if _read_exact(file_handle, 1) != b"\xff":
        raise FileSafetyError("image_corrupt", "图片文件损坏")
    marker = _read_exact(file_handle, 1)[0]
    while marker == 0xFF:
        marker = _read_exact(file_handle, 1)[0]
    if marker == 0x00:
        raise FileSafetyError("image_corrupt", "图片文件损坏")
    return marker


def _validate_jpeg(file_handle, byte_size: int) -> None:
    if _read_exact(file_handle, 2) != b"\xff\xd8":
        raise FileSafetyError("image_corrupt", "图片文件损坏")
    saw_frame = False
    saw_scan = False
    pending_marker: int | None = None
    while pending_marker is not None or file_handle.tell() < byte_size:
        marker = (
            pending_marker
            if pending_marker is not None
            else _next_jpeg_marker(file_handle)
        )
        pending_marker = None
        if marker == 0xD9:
            if file_handle.tell() != byte_size or not (saw_frame and saw_scan):
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            return
        if marker in range(0xD0, 0xD8) or marker == 0x01:
            raise FileSafetyError("image_corrupt", "图片文件损坏")
        segment_length = struct.unpack(">H", _read_exact(file_handle, 2))[0]
        if segment_length < 2 or segment_length - 2 > byte_size - file_handle.tell():
            raise FileSafetyError("image_corrupt", "图片文件损坏")
        payload = _read_exact(file_handle, segment_length - 2)
        if marker in {
            *range(0xC0, 0xC4),
            *range(0xC5, 0xC8),
            *range(0xC9, 0xCC),
            *range(0xCD, 0xD0),
        }:
            if len(payload) < 6 or struct.unpack(">HH", payload[1:5]) == (0, 0):
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            height, width = struct.unpack(">HH", payload[1:5])
            if width == 0 or height == 0:
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            saw_frame = True
        if marker != 0xDA:
            continue
        saw_scan = True
        while file_handle.tell() < byte_size:
            value = _read_exact(file_handle, 1)[0]
            if value != 0xFF:
                continue
            following = _read_exact(file_handle, 1)[0]
            while following == 0xFF:
                following = _read_exact(file_handle, 1)[0]
            if following == 0x00 or following in range(0xD0, 0xD8):
                continue
            pending_marker = following
            break
    raise FileSafetyError("image_corrupt", "图片文件损坏")


def _validate_webp(file_handle, byte_size: int) -> None:
    header = _read_exact(file_handle, 12)
    if header[:4] != b"RIFF" or header[8:12] != b"WEBP":
        raise FileSafetyError("image_corrupt", "图片文件损坏")
    declared_size = struct.unpack("<I", header[4:8])[0] + 8
    if declared_size != byte_size:
        raise FileSafetyError("image_corrupt", "图片文件损坏")
    saw_image_payload = False
    while file_handle.tell() < byte_size:
        chunk_type, chunk_size = struct.unpack("<4sI", _read_exact(file_handle, 8))
        if chunk_size > byte_size - file_handle.tell():
            raise FileSafetyError("image_corrupt", "图片文件损坏")
        prefix = _read_exact(file_handle, min(chunk_size, 10))
        remaining = chunk_size - len(prefix)
        while remaining:
            chunk = _read_exact(file_handle, min(remaining, 64 * 1024))
            remaining -= len(chunk)
        if chunk_size % 2:
            _read_exact(file_handle, 1)
        if chunk_type == b"VP8L":
            if (
                len(prefix) < 5
                or prefix[0] != 0x2F
                or (int.from_bytes(prefix[1:5], "little") >> 29) != 0
            ):
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            saw_image_payload = True
        elif chunk_type == b"VP8 ":
            if len(prefix) < 10 or prefix[3:6] != b"\x9d\x01\x2a":
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            width, height = struct.unpack("<HH", prefix[6:10])
            if width & 0x3FFF == 0 or height & 0x3FFF == 0:
                raise FileSafetyError("image_corrupt", "图片文件损坏")
            saw_image_payload = True
    if file_handle.tell() != byte_size or not saw_image_payload:
        raise FileSafetyError("image_corrupt", "图片文件损坏")


def _validate_text_payload(path: Path) -> None:
    try:
        with path.open("rb") as file_handle:
            sample = file_handle.read(64 * 1024)
        if b"\0" in sample:
            raise FileSafetyError("file_mime_mismatch", "文件类型与声明不一致")
        sample.decode("utf-8-sig")
    except UnicodeDecodeError as exception:
        raise FileSafetyError(
            "file_encoding_unsupported", "文本必须使用 UTF-8"
        ) from exception


def _validate_office_archive(
    path: Path, extension: str, header: bytes, limits: ProcessingLimits
) -> None:
    if header.startswith(OLE_COMPOUND_HEADER):
        raise FileSafetyError("file_encrypted", "文件已加密或受密码保护")
    if not header.startswith(b"PK"):
        raise FileSafetyError("file_corrupt", "Office 文件损坏")
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > limits.max_archive_entries:
                raise FileSafetyError("archive_bomb_detected", "压缩包超过安全上限")
            total_uncompressed = 0
            for member in members:
                _validate_archive_member(member.filename)
                if member.flag_bits & 0x1:
                    raise FileSafetyError("file_encrypted", "文件已加密或受密码保护")
                total_uncompressed += member.file_size
                if total_uncompressed > limits.max_archive_uncompressed_bytes:
                    raise FileSafetyError("archive_bomb_detected", "压缩包超过安全上限")
                if member.file_size:
                    ratio = member.file_size / max(member.compress_size, 1)
                    if ratio > limits.max_archive_compression_ratio:
                        raise FileSafetyError(
                            "archive_bomb_detected", "压缩包压缩率超过安全上限"
                        )
            if archive.testzip() is not None:
                raise FileSafetyError("file_corrupt", "Office 文件损坏")
            content_type_member = archive.getinfo("[Content_Types].xml")
            if content_type_member.file_size > limits.max_office_xml_member_bytes:
                raise FileSafetyError(
                    "office_xml_member_too_large", "Office XML 部件超过安全上限"
                )
            with archive.open(content_type_member) as content_type_handle:
                content_types = content_type_handle.read(
                    limits.max_office_xml_member_bytes + 1
                )
            if len(content_types) > limits.max_office_xml_member_bytes:
                raise FileSafetyError(
                    "office_xml_member_too_large", "Office XML 部件超过安全上限"
                )
    except FileSafetyError:
        raise
    except (BadZipFile, KeyError, OSError, RuntimeError) as exception:
        raise FileSafetyError("file_corrupt", "Office 文件损坏") from exception
    if b"<!DOCTYPE" in content_types.upper() or b"<!ENTITY" in content_types.upper():
        raise FileSafetyError("unsafe_xml_detected", "文档包含不安全 XML")
    try:
        root = ElementTree.fromstring(content_types)
    except ElementTree.ParseError as exception:
        raise FileSafetyError("file_corrupt", "Office 文件损坏") from exception
    declared_types = {
        value.lower()
        for element in root.iter()
        if (value := element.attrib.get("ContentType"))
    }
    marker = OFFICE_CONTENT_MARKERS[extension]
    if not any(marker in declared_type for declared_type in declared_types):
        raise FileSafetyError("file_mime_mismatch", "Office 内容类型与扩展名不一致")


def _validate_archive_member(filename: str) -> None:
    normalized = filename.replace("\\", "/")
    member_path = PurePosixPath(normalized)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise FileSafetyError("archive_member_invalid", "压缩包包含非法路径")
