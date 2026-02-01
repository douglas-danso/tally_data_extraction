import io

import httpx
import pdfplumber


async def download_file(url: str) -> bytes:
    """Download a file from a Tally-hosted URL."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        return response.content


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF using pdfplumber."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = [
            page.extract_text()
            for page in pdf.pages
            if page.extract_text()
        ]
    return "\n\n".join(pages)
