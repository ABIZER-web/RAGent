"""
PHASE 1 — Document Ingestion
Loads PDF / DOCX / TXT / CSV files, extracts text, and splits into
overlapping chunks. Pure Python where possible — minimal dependencies.
"""

import csv
import io
from pypdf import PdfReader
from docx import Document as DocxDocument


def load_pdf_pages(file_path: str):
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"page": i, "text": text})
    return pages


def load_docx_pages(file_path: str):
    doc = DocxDocument(file_path)
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [{"page": 1, "text": full_text}] if full_text.strip() else []


def load_txt_pages(file_path: str):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return [{"page": 1, "text": text}] if text.strip() else []


def load_csv_pages(file_path: str):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        rows = [", ".join(row) for row in reader]
    text = "\n".join(rows)
    return [{"page": 1, "text": text}] if text.strip() else []


LOADERS = {
    ".pdf": load_pdf_pages,
    ".docx": load_docx_pages,
    ".txt": load_txt_pages,
    ".csv": load_csv_pages,
}


def split_text(text: str, chunk_size: int = 250, chunk_overlap: int = 40):
    """Sliding-window word chunker. chunk_size/overlap measured in words."""
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(1, chunk_size - chunk_overlap)
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        if i + chunk_size >= len(words):
            break
        i += step
    return chunks


def chunk_document(file_path: str, source_name: str, chunk_size: int = 250, chunk_overlap: int = 40):
    """
    Loads any supported file type and splits it into overlapping text chunks.
    Each chunk keeps metadata: source filename + page number.
    """
    ext = "." + source_name.rsplit(".", 1)[-1].lower() if "." in source_name else ""
    loader = LOADERS.get(ext)
    if loader is None:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {list(LOADERS.keys())}")

    pages = loader(file_path)

    chunks = []
    for page in pages:
        for text in split_text(page["text"], chunk_size=chunk_size, chunk_overlap=chunk_overlap):
            chunks.append({
                "text": text,
                "source": source_name,
                "page": page["page"],
            })
    return chunks
