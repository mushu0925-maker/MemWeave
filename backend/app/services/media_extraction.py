from __future__ import annotations

import html
import hashlib
import re
import uuid
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import UUID
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.services.ai_gateway import describe_image, transcribe_audio
from app.services.voice_feature_service import build_voice_feature_metadata

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
MAX_EXTRACTED_CHARS = 95_000
TEXT_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "application/json",
    "text/csv",
    "application/xml",
}
BOOK_EXTENSIONS = {".pdf", ".epub", ".docx", ".txt", ".md"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpe", ".jpeg", ".jfif", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".avif", ".ico"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm"}
PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
EPUB_CONTENT_TYPES = {"application/epub+zip"}
DOCX_CONTENT_TYPES = {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


@dataclass(frozen=True)
class ExtractedSource:
    source_type: str
    raw_content: str
    metadata: dict[str, str | int | float | bool | None]


@dataclass(frozen=True)
class StoredUpload:
    file_path: str
    stored_filename: str
    sha256: str
    size_bytes: int


def filename_extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def source_type_from_upload(content_type: str | None, filename: str | None) -> str:
    extension = filename_extension(filename)
    if extension in {".pdf", ".epub", ".docx"} or content_type in PDF_CONTENT_TYPES | EPUB_CONTENT_TYPES | DOCX_CONTENT_TYPES:
        return "book"
    if extension in IMAGE_EXTENSIONS or (content_type and content_type.startswith("image/")):
        return "image"
    if extension in AUDIO_EXTENSIONS or (content_type and content_type.startswith("audio/")):
        return "audio"
    return "file"


def safe_decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def display_filename(filename: str | None) -> str:
    if not filename:
        return "untitled"
    extension = filename_extension(filename)
    if extension:
        return f"uploaded-{uuid.uuid4().hex[:8]}{extension}"
    return f"uploaded-{uuid.uuid4().hex[:8]}"


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _configured_data_dir() -> Path:
    configured = Path(get_settings().local_data_dir)
    if configured.is_absolute():
        return configured
    return _backend_root() / configured


def _safe_stored_filename(filename: str | None) -> str:
    extension = filename_extension(filename) or ".bin"
    stem = Path(filename or "uploaded").stem or "uploaded"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip("._-")[:64] or "uploaded"
    return f"{safe_stem}-{uuid.uuid4().hex[:12]}{extension}"


def _upload_storage_path(*, filename: str | None, profile_id: UUID | None) -> tuple[Path, str]:
    directory = _configured_data_dir() / "uploads" / (str(profile_id) if profile_id else "unassigned")
    directory.mkdir(parents=True, exist_ok=True)
    stored_filename = _safe_stored_filename(filename)
    return directory / stored_filename, stored_filename


def store_uploaded_source_file(data: bytes, *, filename: str | None, profile_id: UUID | None) -> StoredUpload:
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file is larger than 100 MB.",
        )
    path, stored_filename = _upload_storage_path(filename=filename, profile_id=profile_id)
    path.write_bytes(data)
    return StoredUpload(
        file_path=str(path),
        stored_filename=stored_filename,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


async def store_uploaded_source_stream(upload: UploadFile, *, profile_id: UUID | None) -> StoredUpload:
    """Persist an upload while enforcing the size cap before extraction or full buffering."""

    path, stored_filename = _upload_storage_path(filename=upload.filename, profile_id=profile_id)
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("wb") as target:
            while True:
                chunk = await upload.read(UPLOAD_READ_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Uploaded file is larger than 100 MB.",
                    )
                digest.update(chunk)
                target.write(chunk)
    except Exception:
        with suppress(OSError):
            path.unlink()
        raise
    return StoredUpload(
        file_path=str(path),
        stored_filename=stored_filename,
        sha256=digest.hexdigest(),
        size_bytes=total,
    )


def limit_extracted_text(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_EXTRACTED_CHARS:
        return text, False
    return text[:MAX_EXTRACTED_CHARS], True


def extract_pdf_text(data: bytes) -> tuple[str, dict[str, str | int | float | bool | None]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF extraction requires pypdf. Install backend requirements and restart the server.",
        ) from exc

    reader = PdfReader(BytesIO(data))
    page_texts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        if extracted.strip():
            page_texts.append(f"\n\n[Page {index}]\n{extracted.strip()}")
        if sum(len(part) for part in page_texts) >= MAX_EXTRACTED_CHARS:
            break
    text, truncated = limit_extracted_text("".join(page_texts).strip())
    return text, {
        "book_format": "pdf",
        "page_count": len(reader.pages),
        "extracted_chars": len(text),
        "truncated": truncated,
    }


def extract_docx_text(data: bytes) -> tuple[str, dict[str, str | int | float | bool | None]]:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        try:
            xml_data = archive.read("word/document.xml")
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="DOCX file does not contain word/document.xml.",
            ) from exc

    root = ElementTree.fromstring(xml_data)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    extracted, truncated = limit_extracted_text("\n".join(paragraphs))
    return extracted, {
        "book_format": "docx",
        "paragraph_count": len(paragraphs),
        "extracted_chars": len(extracted),
        "truncated": truncated,
    }


def extract_epub_text(data: bytes) -> tuple[str, dict[str, str | int | float | bool | None]]:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        html_names = [
            name
            for name in archive.namelist()
            if name.lower().endswith((".html", ".xhtml", ".htm"))
        ]
        chunks: list[str] = []
        for name in html_names:
            raw = archive.read(name)
            decoded = safe_decode(raw)
            decoded = re.sub(r"<script\b[^>]*>.*?</script>", " ", decoded, flags=re.IGNORECASE | re.DOTALL)
            decoded = re.sub(r"<style\b[^>]*>.*?</style>", " ", decoded, flags=re.IGNORECASE | re.DOTALL)
            decoded = re.sub(r"<[^>]+>", " ", decoded)
            decoded = html.unescape(decoded)
            decoded = re.sub(r"\s+", " ", decoded).strip()
            if decoded:
                chunks.append(f"\n\n[{name}]\n{decoded}")
            if sum(len(part) for part in chunks) >= MAX_EXTRACTED_CHARS:
                break
    extracted, truncated = limit_extracted_text("".join(chunks).strip())
    return extracted, {
        "book_format": "epub",
        "html_file_count": len(html_names),
        "extracted_chars": len(extracted),
        "truncated": truncated,
    }


def extract_book_text(
    data: bytes,
    content_type: str,
    filename: str | None,
) -> tuple[str, dict[str, str | int | float | bool | None]]:
    extension = filename_extension(filename)
    if extension == ".pdf" or content_type in PDF_CONTENT_TYPES:
        return extract_pdf_text(data)
    if extension == ".docx" or content_type in DOCX_CONTENT_TYPES:
        return extract_docx_text(data)
    if extension == ".epub" or content_type in EPUB_CONTENT_TYPES:
        return extract_epub_text(data)
    decoded, truncated = limit_extracted_text(safe_decode(data))
    return decoded, {
        "book_format": extension.lstrip(".") or "text",
        "extracted_chars": len(decoded),
        "truncated": truncated,
    }


def _append_notes(raw_content: str, notes: str) -> str:
    if not notes.strip():
        return raw_content
    return f"{raw_content}\n\nUploader notes:\n{notes.strip()}"


def _media_metadata_block(source_type: str, filename: str | None, content_type: str, size_bytes: int) -> str:
    return (
        f"Uploaded {source_type} source.\n"
        f"Uploaded file token: {display_filename(filename)}\n"
        f"Content type: {content_type}\n"
        f"Size bytes: {size_bytes}"
    )


def extract_uploaded_source(
    data: bytes,
    *,
    filename: str | None,
    content_type: str | None,
    notes: str,
) -> ExtractedSource:
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file is larger than 100 MB.",
        )

    normalized_content_type = content_type or "application/octet-stream"
    source_type = source_type_from_upload(normalized_content_type, filename)
    metadata: dict[str, str | int | float | bool | None] = {
        "filename": filename,
        "content_type": normalized_content_type,
        "size_bytes": len(data),
        "upload_kind": source_type,
    }

    if source_type == "book":
        extracted, extraction_metadata = extract_book_text(data, normalized_content_type, filename)
        metadata.update(extraction_metadata)
        if not extracted.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No readable text could be extracted from this book file.",
            )
        raw_content = (
            f"Long-form memory/reference source.\n"
            f"Content type: {normalized_content_type}\n"
            f"Extracted characters: {metadata.get('extracted_chars')}\n\n"
            f"{extracted}"
        )
        return ExtractedSource(source_type, _append_notes(raw_content, notes), metadata)

    if source_type == "file" and (
        normalized_content_type in TEXT_CONTENT_TYPES
        or (filename or "").lower().endswith((".txt", ".md", ".json", ".csv"))
    ):
        return ExtractedSource(source_type, _append_notes(safe_decode(data), notes), metadata)

    if source_type == "image":
        # 上传成功不等于内容识别成功；无视觉模型时保留元数据和备注，并明确标记未识别。
        # Upload success is separate from visual recognition success.
        image_result = describe_image(data, normalized_content_type, filename, notes)
        if image_result.text:
            metadata["extraction_provider"] = image_result.provider
            metadata["extraction_status"] = "recognized"
            raw_content = (
                f"{_media_metadata_block(source_type, filename, normalized_content_type, len(data))}\n"
                f"Image memory analysis:\n{image_result.text}"
            )
        else:
            error = image_result.error or "empty_model_response"
            metadata["extraction_provider"] = image_result.provider
            metadata["extraction_error"] = error
            if image_result.provider == "vision_disabled":
                metadata["extraction_status"] = "disabled"
                status_line = "视觉/OCR 已关闭：当前只保存图片元数据和上传备注，不读取图中文字或场景。"
                recovery_line = "要识别图片内容，请到设置里开启视觉识别，并确认所选接口支持视觉模型。"
            elif image_result.provider == "vision_not_configured":
                metadata["extraction_status"] = "not_configured"
                if error in {"llm_api_key_missing", "vision_api_key_missing"}:
                    status_line = "视觉/OCR 未配置：缺少可用 API Key，当前无法识别图片内容。"
                elif error == "vision_model_missing":
                    status_line = "视觉/OCR 未配置：缺少视觉模型名称，当前无法识别图片内容。"
                else:
                    status_line = f"视觉/OCR 未配置：{error}"
                recovery_line = "请在设置里填写 API Key、接口地址和视觉模型后重试。"
            else:
                metadata["extraction_status"] = "failed"
                status_line = f"视觉/OCR 调用失败：{error}"
                recovery_line = "图片已保存为原始资料；请检查视觉模型、接口地址、代理和模型服务后重新提取。"
            metadata["extraction_hint"] = recovery_line
            raw_content = (
                f"{_media_metadata_block(source_type, filename, normalized_content_type, len(data))}\n"
                f"{status_line}\n"
                f"{recovery_line}"
            )
        return ExtractedSource(source_type, _append_notes(raw_content, notes), metadata)

    if source_type == "audio":
        # 音频先走 ASR；未配置时只把上传事实和备注交给后续人格蒸馏。
        # Audio uses ASR when configured; voice metadata remains descriptive only.
        audio_result = transcribe_audio(data, filename, normalized_content_type)
        if audio_result and audio_result.text:
            metadata["extraction_provider"] = audio_result.provider
            metadata["extraction_status"] = "transcribed"
            metadata.update(
                build_voice_feature_metadata(
                    transcript=audio_result.text,
                    notes=notes,
                    asr_status="transcribed",
                )
            )
            raw_content = (
                f"{_media_metadata_block(source_type, filename, normalized_content_type, len(data))}\n"
                f"Audio transcript for voice/persona distillation:\n{audio_result.text}"
            )
        else:
            metadata["extraction_provider"] = audio_result.provider if audio_result else "not_configured"
            metadata["extraction_error"] = audio_result.error if audio_result else None
            metadata["extraction_status"] = "not_configured" if audio_result is None else "failed"
            metadata.update(
                build_voice_feature_metadata(
                    transcript="",
                    notes=notes,
                    asr_status=str(metadata["extraction_status"]),
                )
            )
            raw_content = (
                f"{_media_metadata_block(source_type, filename, normalized_content_type, len(data))}\n"
                "Audio extraction status: no usable ASR transcript yet. Use uploader notes as memory evidence."
            )
        return ExtractedSource(source_type, _append_notes(raw_content, notes), metadata)

    raw_content = (
        f"{_media_metadata_block(source_type, filename, normalized_content_type, len(data))}\n"
        "Unsupported binary file for direct text extraction. Use uploader notes as memory evidence."
    )
    return ExtractedSource(source_type, _append_notes(raw_content, notes), metadata)
