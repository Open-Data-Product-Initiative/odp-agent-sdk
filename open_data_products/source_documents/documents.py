"""Load supported source documents into normalized text records."""

from __future__ import annotations

import base64
import binascii
import csv
from email import policy
from email.parser import BytesParser
import hashlib
import importlib
import io
from pathlib import Path
import re
from typing import Dict, List, Tuple
from xml.etree import ElementTree
import zlib
from zipfile import BadZipFile, ZipFile

TEXT_SUFFIXES = (".md", ".txt", ".yaml", ".yml", ".json")
CSV_ROW_LIMIT = 50
PORTFOLIO_DOCUMENT_SUFFIXES = TEXT_SUFFIXES + (
    ".csv",
    ".eml",
    ".msg",
    ".docx",
    ".pptx",
    ".xlsx",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
)
MSG_INSTALL_WARNING = "install open-data-products[email] to enable .msg extraction."
PDF_TEXT_WARNING = "no embedded text found; OCR or vision extraction is not enabled."
IMAGE_TEXT_WARNING = "OCR or vision extraction is not enabled."
OOXML_TEXT_WARNING = "file extension does not match a readable OOXML document."
OLE_COMPOUND_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
PDF_HEADER = b"%PDF-"
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
JPEG_HEADER = b"\xff\xd8\xff"
PDF_STREAM_PATTERN = re.compile(rb"stream\r?\n(.*?)\r?\n?endstream", re.S)
PDF_TEXT_BLOCK_PATTERN = re.compile(r"BT(.*?)ET", re.S)
OOXML_SUFFIXES = (".docx", ".pptx", ".xlsx")


def load_source_documents(path: Path) -> List[Dict[str, str]]:
    """Load one source path into portfolio-compatible source records."""
    source_type, detection_method = detect_source_type(path)
    if source_type in TEXT_SUFFIXES:
        return [_text_record(path, detection_method=detection_method)]
    if source_type == ".csv":
        return [_csv_record(path, detection_method=detection_method)]
    if source_type == ".eml":
        return [_email_record(path, detection_method=detection_method)]
    if source_type == ".msg":
        return [_msg_record(path, detection_method=detection_method)]
    if source_type in OOXML_SUFFIXES and detection_method == "extension":
        detected_ooxml = _detect_ooxml_type(path)
        if detected_ooxml != source_type:
            return [
                _skipped_ooxml_record(
                    path,
                    source_type,
                    detection_method=detection_method,
                )
            ]
    if source_type == ".docx":
        return [_docx_record(path, detection_method=detection_method)]
    if source_type == ".pptx":
        return [_pptx_record(path, detection_method=detection_method)]
    if source_type == ".xlsx":
        return [_xlsx_record(path, detection_method=detection_method)]
    if source_type == ".pdf":
        return [_pdf_record(path, detection_method=detection_method)]
    if source_type in {".png", ".jpg", ".jpeg"}:
        return [
            _skipped_image_record(
                path,
                source_type,
                detection_method=detection_method,
            )
        ]
    return []


def detect_source_type(path: Path) -> Tuple[str, str]:
    """Detect a supported source type using content signatures first."""
    with path.open("rb") as handle:
        header = handle.read(4096)
    if header.startswith(OLE_COMPOUND_HEADER):
        return ".msg", "ole-compound-header"
    if header.startswith(PDF_HEADER):
        return ".pdf", "pdf-header"
    if header.startswith(PNG_HEADER):
        return ".png", "png-header"
    if header.startswith(JPEG_HEADER):
        return ".jpg", "jpeg-header"
    ooxml_type = _detect_ooxml_type(path)
    if ooxml_type:
        return ooxml_type, "ooxml-container"
    if _looks_like_eml(header):
        return ".eml", "rfc822-headers"
    if _looks_like_csv(header):
        return ".csv", "csv-sniffer"
    suffix = path.suffix.lower()
    if suffix in PORTFOLIO_DOCUMENT_SUFFIXES:
        return suffix, "extension"
    return "", "unknown"


def _looks_like_eml(header: bytes) -> bool:
    try:
        text = header.decode("utf-8", errors="ignore").lower()
    except UnicodeDecodeError:
        return False
    if "\n" not in text and "\r" not in text:
        return False
    header_names = ("subject:", "from:", "to:", "date:", "content-type:")
    return sum(1 for name in header_names if name in text) >= 2


def _looks_like_csv(header: bytes) -> bool:
    try:
        sample = header.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    if not sample.strip() or "\n" not in sample:
        return False
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        return False
    if dialect.delimiter not in {",", ";", "\t"}:
        return False
    rows = list(csv.reader(io.StringIO(sample), dialect))
    non_empty_rows = [row for row in rows if any(cell.strip() for cell in row)]
    if len(non_empty_rows) < 2:
        return False
    if not _looks_like_csv_header(non_empty_rows[0]):
        return False
    width = len(non_empty_rows[0])
    if width < 2:
        return False
    return all(len(row) == width for row in non_empty_rows[:5])


def _looks_like_csv_header(row: List[str]) -> bool:
    non_empty_cells = [cell.strip() for cell in row if cell.strip()]
    if len(non_empty_cells) < 2:
        return False
    for cell in non_empty_cells:
        if len(cell) > 64:
            return False
        if re.search(r"[.!?]", cell):
            return False
    return True


def _detect_ooxml_type(path: Path) -> str:
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
    except (BadZipFile, OSError):
        return ""
    if "word/document.xml" in names:
        return ".docx"
    if "xl/workbook.xml" in names and any(
        name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        for name in names
    ):
        return ".xlsx"
    if "ppt/presentation.xml" in names or any(
        name.startswith("ppt/slides/slide") and name.endswith(".xml")
        for name in names
    ):
        return ".pptx"
    return ""


def _text_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    text, warning = _read_text_file(path)
    return _source_record(
        path,
        text=text,
        source_type=path.suffix.lower().lstrip(".") or "text",
        source_unit="file",
        source_unit_id="1",
        title=path.stem,
        detection_method=detection_method,
        warning=warning,
    )


def _csv_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    text, warning = _csv_text(path)
    return _source_record(
        path,
        text=text,
        source_type="csv",
        source_unit="table",
        source_unit_id="1",
        title=path.stem,
        detection_method=detection_method,
        warning=warning,
    )


def _read_text_file(path: Path) -> Tuple[str, str]:
    content = path.read_bytes()
    try:
        return _clean_text(content.decode("utf-8-sig")), ""
    except UnicodeDecodeError:
        return (
            _clean_text(content.decode("latin-1")),
            f"Decoded text source {path} as Latin-1 after UTF-8 failed.",
        )


def _clean_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)


def _csv_text(path: Path) -> Tuple[str, str]:
    content, warning = _read_text_file(path)
    try:
        dialect = csv.Sniffer().sniff(content)
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(content), dialect))
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return "", warning
    header = [cell.strip() for cell in rows[0]]
    data_rows = [[cell.strip() for cell in row] for row in rows[1:]]
    included_rows = data_rows[:CSV_ROW_LIMIT]
    lines = [
        f"CSV table: {path.name}",
        f"Columns: {', '.join(header)}",
        f"Rows: {len(data_rows)}",
        f"Rows included: {len(included_rows)}",
    ]
    omitted = max(len(data_rows) - len(included_rows), 0)
    if omitted:
        lines.append(f"Rows omitted: {omitted}")
    lines.extend(_markdown_table(header, included_rows))
    return "\n".join(lines), warning


def _markdown_table(header: List[str], rows: List[List[str]]) -> List[str]:
    if not header:
        return []
    normalized_rows = [_normalize_row(row, len(header)) for row in rows]
    table = [
        "| " + " | ".join(_escape_table_cell(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _item in header) + " |",
    ]
    for row in normalized_rows:
        table.append(
            "| " + " | ".join(_escape_table_cell(cell) for cell in row) + " |"
        )
    return table


def _normalize_row(row: List[str], width: int) -> List[str]:
    normalized = list(row[:width])
    while len(normalized) < width:
        normalized.append("")
    return normalized


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _docx_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    text = "\n".join(_ooxml_text(path, "word/document.xml"))
    return _source_record(
        path,
        text=text,
        source_type="docx",
        source_unit="document",
        source_unit_id="1",
        title=path.stem,
        detection_method=detection_method,
    )


def _pptx_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    try:
        with ZipFile(path) as archive:
            slide_names = sorted(
                name
                for name in archive.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )
    except (BadZipFile, OSError):
        slide_names = []
    slide_sections: List[str] = []
    for index, slide_name in enumerate(slide_names, start=1):
        text = "\n".join(_ooxml_text(path, slide_name))
        if not text.strip():
            continue
        slide_sections.append(f"Slide {index}:\n{text}")
    return _source_record(
        path,
        text="\n\n".join(slide_sections),
        source_type="pptx",
        source_unit="deck",
        source_unit_id="1",
        title=path.stem,
        detection_method=detection_method,
    )


def _xlsx_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    text = "\n\n".join(_xlsx_sheet_sections(path)).strip()
    return _source_record(
        path,
        text=text,
        source_type="xlsx",
        source_unit="workbook",
        source_unit_id="1",
        title=path.stem,
        detection_method=detection_method,
    )


def _xlsx_sheet_sections(path: Path) -> List[str]:
    try:
        with ZipFile(path) as archive:
            shared_strings = _xlsx_shared_strings(archive)
            sheet_map = _xlsx_sheet_relationships(archive)
            sheets = _xlsx_workbook_sheets(archive, sheet_map)
            sections = []
            for sheet_name, sheet_path in sheets:
                rows = _xlsx_sheet_rows(archive, sheet_path, shared_strings)
                if not rows:
                    continue
                sections.append(_xlsx_sheet_text(sheet_name, rows))
            return sections
    except (BadZipFile, OSError):
        return []


def _xlsx_shared_strings(archive: ZipFile) -> List[str]:
    try:
        content = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return []
    strings = []
    for item in root.iter():
        if not item.tag.endswith("}si"):
            continue
        parts = [
            text_element.text or ""
            for text_element in item.iter()
            if text_element.tag.endswith("}t")
        ]
        strings.append("".join(parts))
    return strings


def _xlsx_sheet_relationships(archive: ZipFile) -> Dict[str, str]:
    try:
        content = archive.read("xl/_rels/workbook.xml.rels")
    except KeyError:
        return {}
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return {}
    relationships = {}
    for relationship in root:
        relationship_id = relationship.attrib.get("Id")
        target = relationship.attrib.get("Target")
        if not relationship_id or not target:
            continue
        relationships[relationship_id] = _xlsx_target_path(target)
    return relationships


def _xlsx_target_path(target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return "xl/" + target.lstrip("/")


def _xlsx_workbook_sheets(
    archive: ZipFile,
    sheet_map: Dict[str, str],
) -> List[Tuple[str, str]]:
    try:
        content = archive.read("xl/workbook.xml")
    except KeyError:
        return []
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return []
    sheets = []
    for sheet in root.iter():
        if not sheet.tag.endswith("}sheet"):
            continue
        name = sheet.attrib.get("name") or "Sheet"
        relationship_id = (
            sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            or sheet.attrib.get("r:id")
        )
        sheet_path = sheet_map.get(relationship_id or "")
        if sheet.attrib.get("state") in {"hidden", "veryHidden"}:
            continue
        if sheet_path:
            sheets.append((name, sheet_path))
    return sheets


def _xlsx_sheet_rows(
    archive: ZipFile,
    sheet_path: str,
    shared_strings: List[str],
) -> List[List[str]]:
    try:
        content = archive.read(sheet_path)
    except KeyError:
        return []
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return []
    rows = []
    for row in root.iter():
        if not row.tag.endswith("}row"):
            continue
        values = []
        for cell in row:
            if cell.tag.endswith("}c"):
                values.append(_xlsx_cell_value(cell, shared_strings))
        if any(value.strip() for value in values):
            rows.append(values)
    return rows


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: List[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        parts = [
            text_element.text or ""
            for text_element in cell.iter()
            if text_element.tag.endswith("}t")
        ]
        return "".join(parts).strip()
    value = ""
    for child in cell:
        if child.tag.endswith("}v") and child.text is not None:
            value = child.text
            break
    if cell_type == "s":
        try:
            return shared_strings[int(value)].strip()
        except (IndexError, ValueError):
            return ""
    return value.strip()


def _xlsx_sheet_text(sheet_name: str, rows: List[List[str]]) -> str:
    header = [cell.strip() for cell in rows[0]]
    data_rows = [[cell.strip() for cell in row] for row in rows[1:]]
    included_rows = data_rows[:CSV_ROW_LIMIT]
    lines = [
        f"Sheet: {sheet_name}",
        f"Columns: {', '.join(header)}",
        f"Rows: {len(data_rows)}",
        f"Rows included: {len(included_rows)}",
    ]
    omitted = max(len(data_rows) - len(included_rows), 0)
    if omitted:
        lines.append(f"Rows omitted: {omitted}")
    lines.extend(_markdown_table(header, included_rows))
    return "\n".join(lines)


def _pdf_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    text = "\n".join(_pdf_embedded_text(path)).strip()
    if not text:
        return _skipped_pdf_record(path, detection_method=detection_method)
    return _source_record(
        path,
        text=text,
        source_type="pdf",
        source_unit="document",
        source_unit_id="1",
        title=path.stem,
        detection_method=detection_method,
    )


def _pdf_embedded_text(path: Path) -> List[str]:
    try:
        content = path.read_bytes()
    except OSError:
        return []
    parts: List[str] = []
    for match in PDF_STREAM_PATTERN.finditer(content):
        dictionary = _pdf_stream_dictionary(content, match.start())
        stream = _decode_pdf_stream(match.group(1), dictionary)
        if stream is None:
            continue
        parts.extend(_pdf_text_from_stream(stream))
    return parts


def _pdf_stream_dictionary(content: bytes, stream_start: int) -> bytes:
    prefix = content[max(0, stream_start - 2048) : stream_start]
    start = prefix.rfind(b"<<")
    end = prefix.rfind(b">>")
    if start == -1 or end == -1 or end < start:
        return b""
    return prefix[start : end + 2]


def _decode_pdf_stream(stream: bytes, dictionary: bytes) -> bytes:
    decoded = stream.strip()
    if b"/ASCII85Decode" in dictionary:
        try:
            decoded = base64.a85decode(decoded, adobe=True)
        except (ValueError, binascii.Error):
            return b""
    if b"/FlateDecode" in dictionary:
        try:
            decoded = zlib.decompress(decoded)
        except zlib.error:
            return b""
    return decoded


def _pdf_text_from_stream(stream: bytes) -> List[str]:
    try:
        text = stream.decode("latin-1")
    except UnicodeDecodeError:
        return []
    parts: List[str] = []
    for block in PDF_TEXT_BLOCK_PATTERN.findall(text):
        parts.extend(_pdf_literal_strings(block))
    return [part.strip() for part in parts if part.strip()]


def _pdf_literal_strings(text: str) -> List[str]:
    literals: List[str] = []
    index = 0
    while index < len(text):
        if text[index] != "(":
            index += 1
            continue
        value, index = _read_pdf_literal(text, index + 1)
        literals.append(value)
    return literals


def _read_pdf_literal(text: str, index: int) -> Tuple[str, int]:
    value: List[str] = []
    depth = 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            if index + 1 >= len(text):
                break
            escaped = text[index + 1]
            value.append(_pdf_escape_value(escaped))
            index += 2
            continue
        if char == "(":
            depth += 1
            value.append(char)
            index += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return "".join(value), index + 1
            value.append(char)
            index += 1
            continue
        value.append(char)
        index += 1
    return "".join(value), index


def _pdf_escape_value(value: str) -> str:
    escapes = {
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "b": "\b",
        "f": "\f",
        "\\": "\\",
        "(": "(",
        ")": ")",
    }
    return escapes.get(value, value)


def _ooxml_text(path: Path, member: str) -> List[str]:
    try:
        with ZipFile(path) as archive:
            content = archive.read(member)
    except (BadZipFile, KeyError, OSError):
        return []
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return []
    parts: List[str] = []
    for element in root.iter():
        if element.tag.endswith("}t") and element.text:
            value = element.text.strip()
            if value:
                parts.append(value)
    return parts


def _email_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    with path.open("rb") as handle:
        message = BytesParser(policy=policy.default).parse(handle)
    subject = str(message.get("subject") or path.stem)
    text = _message_body_text(message).strip()
    metadata = [
        f"Subject: {subject}",
        f"From: {message.get('from', '')}",
        f"To: {message.get('to', '')}",
        f"Date: {message.get('date', '')}",
    ]
    content = "\n".join([line for line in metadata if line.strip()]) + "\n\n" + text
    return _source_record(
        path,
        text=content.strip(),
        source_type="eml",
        source_unit="message",
        source_unit_id="1",
        title=subject,
        detection_method=detection_method,
    )


def _msg_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    extract_msg = _optional_extract_msg()
    if extract_msg is None:
        return _skipped_msg_record(path, detection_method=detection_method)
    try:
        message = _open_msg_message(extract_msg, path)
        subject = _msg_value(message, "subject") or path.stem
        sender = _msg_value(message, "sender")
        to = _msg_value(message, "to")
        date = _msg_value(message, "date")
        body = _msg_value(message, "body")
        metadata = [
            f"Subject: {subject}",
            f"From: {sender}",
            f"To: {to}",
            f"Date: {date}",
        ]
        content = "\n".join([line for line in metadata if line.strip()])
        if body.strip():
            content = f"{content}\n\n{body.strip()}" if content else body.strip()
        return _source_record(
            path,
            text=content.strip(),
            source_type="msg",
            source_unit="message",
            source_unit_id="1",
            title=subject,
            detection_method=detection_method,
        )
    except Exception as exc:
        return _skipped_msg_record(
            path,
            detection_method=detection_method,
            reason=f"{type(exc).__name__}: {exc}",
        )
    finally:
        close = locals().get("message")
        if close is not None and hasattr(close, "close"):
            close.close()


def _optional_extract_msg() -> object:
    try:
        return importlib.import_module("extract_msg")
    except ImportError:
        return None


def _open_msg_message(extract_msg: object, path: Path) -> object:
    opener = getattr(extract_msg, "openMsg", None) or getattr(extract_msg, "Message")
    return opener(str(path))


def _msg_value(message: object, name: str) -> str:
    value = getattr(message, name, "")
    if callable(value):
        value = value()
    return str(value or "")


def _message_body_text(message: object) -> str:
    if getattr(message, "is_multipart", lambda: False)():
        parts = []
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_type() != "text/plain":
                continue
            disposition = part.get_content_disposition()
            if disposition == "attachment":
                continue
            payload = part.get_content()
            if isinstance(payload, str):
                parts.append(payload)
        return "\n\n".join(parts)
    payload = message.get_content()
    return payload if isinstance(payload, str) else ""


def _skipped_msg_record(
    path: Path,
    *,
    detection_method: str,
    reason: str = MSG_INSTALL_WARNING,
) -> Dict[str, str]:
    return {
        "path": str(path),
        "sourceId": _source_id(path, "message", "1"),
        "sourceType": "msg",
        "detectionMethod": detection_method,
        "skipped": "true",
        "warning": f"Skipped Outlook .msg source {path}: {reason}",
    }


def _skipped_pdf_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    return {
        "path": str(path),
        "sourceId": _source_id(path, "document", "1"),
        "sourceType": "pdf",
        "detectionMethod": detection_method,
        "skipped": "true",
        "warning": f"Skipped PDF source {path}: {PDF_TEXT_WARNING}",
    }


def _skipped_image_record(
    path: Path,
    source_type: str,
    *,
    detection_method: str,
) -> Dict[str, str]:
    return {
        "path": str(path),
        "sourceId": _source_id(path, "image", "1"),
        "sourceType": source_type.lstrip("."),
        "detectionMethod": detection_method,
        "skipped": "true",
        "warning": f"Skipped image source {path}: {IMAGE_TEXT_WARNING}",
    }


def _skipped_ooxml_record(
    path: Path,
    source_type: str,
    *,
    detection_method: str,
) -> Dict[str, str]:
    return {
        "path": str(path),
        "sourceId": _source_id(path, source_type.lstrip("."), "1"),
        "sourceType": source_type.lstrip("."),
        "detectionMethod": detection_method,
        "skipped": "true",
        "warning": f"Skipped Office source {path}: {OOXML_TEXT_WARNING}",
    }


def _source_record(
    path: Path,
    *,
    text: str,
    source_type: str,
    source_unit: str,
    source_unit_id: str,
    title: str,
    detection_method: str,
    warning: str = "",
) -> Dict[str, str]:
    text = _clean_text(text)
    record = {
        "path": str(path),
        "sourceId": _source_id(path, source_unit, source_unit_id),
        "text": text,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "sourceType": source_type,
        "detectionMethod": detection_method,
        "sourceUnit": source_unit,
        "sourceUnitId": source_unit_id,
        "title": title,
    }
    if warning:
        record["warning"] = warning
    return record


def _source_id(path: Path, source_unit: str, source_unit_id: str) -> str:
    return f"{path}#{source_unit}-{source_unit_id}"
