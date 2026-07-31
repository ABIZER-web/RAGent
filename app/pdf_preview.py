"""
PDF preview + highlighting.
Renders a specific page of an uploaded PDF as an image, with the retrieved
chunk's text highlighted — so a citation can be visually verified.
Uses PyMuPDF (no external binaries needed, unlike poppler-based tools).
"""

import os
import base64
import fitz  # PyMuPDF


def render_highlighted_page(pdf_path: str, page_number: int, highlight_text: str, zoom: float = 1.6) -> str:
    """
    Returns a base64-encoded PNG of the given page, with highlight_text
    highlighted if found. page_number is 1-indexed.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    if page_number < 1 or page_number > len(doc):
        raise ValueError(f"Page {page_number} out of range (doc has {len(doc)} pages).")

    page = doc[page_number - 1]

    # Try highlighting the first ~120 chars of the chunk (long strings rarely
    # match exactly due to whitespace/line-break differences in extraction).
    snippet = highlight_text.strip()[:120]
    quads = page.search_for(snippet, quads=True)

    if not quads and len(snippet) > 40:
        # fall back to a shorter snippet — more likely to find a literal match
        snippet_short = snippet[:40]
        quads = page.search_for(snippet_short, quads=True)

    for quad in quads:
        annot = page.add_highlight_annot(quad)
        annot.set_colors(stroke=(1, 0.85, 0.2))
        annot.update()

    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img_bytes = pix.tobytes("png")
    doc.close()

    return base64.b64encode(img_bytes).decode("utf-8")
