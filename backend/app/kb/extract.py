"""Download a PDF and extract clean text."""
from __future__ import annotations

import io
import re

import httpx
from pypdf import PdfReader


def download_pdf(url: str, timeout: float = 60.0) -> bytes:
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return clean_text("\n".join(pages))


def clean_text(text: str) -> str:
    # Normalize whitespace; drop the standard COPSA header line noise.
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln).strip()
