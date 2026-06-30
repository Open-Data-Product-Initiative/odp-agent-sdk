"""Load supported source documents into normalized text records."""

from __future__ import annotations

from email import policy
from email.parser import BytesParser
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

TEXT_SUFFIXES = (".md", ".txt", ".yaml", ".yml", ".json")
PORTFOLIO_DOCUMENT_SUFFIXES = TEXT_SUFFIXES + (".eml", ".msg", ".docx", ".pptx")
MSG_INSTALL_WARNING = "install open-data-products[email] to enable .msg extraction."
OLE_COMPOUND_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def load_source_documents(path: Path) -> List[Dict[str, str]]:
    """Load one source path into portfolio-compatible source records."""
    source_type, detection_method = detect_source_type(path)
    if source_type in TEXT_SUFFIXES:
        return [_text_record(path, detection_method=detection_method)]
    if source_type == ".eml":
        return [_email_record(path, detection_method=detection_method)]
    if source_type == ".msg":
        return [_skipped_msg_record(path, detection_method=detection_method)]
    if source_type == ".docx":
        return [_docx_record(path, detection_method=detection_method)]
    if source_type == ".pptx":
        return [_pptx_record(path, detection_method=detection_method)]
    return []


def detect_source_type(path: Path) -> Tuple[str, str]:
    """Detect a supported source type using content signatures first."""
    with path.open("rb") as handle:
        header = handle.read(4096)
    if header.startswith(OLE_COMPOUND_HEADER):
        return ".msg", "ole-compound-header"
    ooxml_type = _detect_ooxml_type(path)
    if ooxml_type:
        return ooxml_type, "ooxml-container"
    if _looks_like_eml(header):
        return ".eml", "rfc822-headers"
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


def _detect_ooxml_type(path: Path) -> str:
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
    except (BadZipFile, OSError):
        return ""
    if "word/document.xml" in names:
        return ".docx"
    if "ppt/presentation.xml" in names or any(
        name.startswith("ppt/slides/slide") and name.endswith(".xml")
        for name in names
    ):
        return ".pptx"
    return ""


def _text_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8")
    return _source_record(
        path,
        text=text,
        source_type=path.suffix.lower().lstrip(".") or "text",
        source_unit="file",
        source_unit_id="1",
        title=path.stem,
        detection_method=detection_method,
    )


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


def _skipped_msg_record(path: Path, *, detection_method: str) -> Dict[str, str]:
    return {
        "path": str(path),
        "sourceId": _source_id(path, "message", "1"),
        "sourceType": "msg",
        "detectionMethod": detection_method,
        "skipped": "true",
        "warning": f"Skipped Outlook .msg source {path}: {MSG_INSTALL_WARNING}",
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
) -> Dict[str, str]:
    return {
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


def _source_id(path: Path, source_unit: str, source_unit_id: str) -> str:
    return f"{path}#{source_unit}-{source_unit_id}"
