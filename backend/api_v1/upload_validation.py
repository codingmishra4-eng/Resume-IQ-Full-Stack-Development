"""API boundary guards; the existing parser remains unchanged."""

import io
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

from backend.api_v1.errors import APIError

MAX_DOCX_ENTRIES = 1000
MAX_DOCX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 200


def validate_content(data: bytes, suffix: str) -> None:
    if suffix == ".pdf":
        # PDF permits leading bytes before its signature; cap that search.
        if b"%PDF-" not in data[:1024]:
            raise APIError("invalid_file", "The file content does not match a PDF document.")
        return

    try:
        with ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                raise APIError("unsafe_document", "The DOCX archive contains too many entries.")
            names = [entry.filename for entry in entries]
            if len(set(names)) != len(names):
                raise APIError("unsafe_document", "The DOCX archive contains duplicate entries.")
            if not {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}.issubset(names):
                raise APIError("invalid_file", "Please upload a valid DOCX document.")
            expanded = 0
            for entry in entries:
                expanded += entry.file_size
                if (entry.flag_bits & 1 or entry.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                        or expanded > MAX_DOCX_EXPANDED_BYTES
                        or entry.file_size > max(entry.compress_size, 1) * MAX_DOCX_COMPRESSION_RATIO):
                    raise APIError("unsafe_document", "The DOCX archive exceeds safe processing limits.")
                # No archive entries are extracted to filesystem paths.
    except (BadZipFile, OSError, ValueError) as exc:
        raise APIError("invalid_file", "Please upload a valid DOCX document.") from exc
