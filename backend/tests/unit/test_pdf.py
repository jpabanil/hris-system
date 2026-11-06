"""PDF rendering uses the local Homebrew pango libraries on macOS."""

from app.shared.documents import html_to_pdf


def test_html_to_pdf_returns_a_pdf() -> None:
    pdf = html_to_pdf("<html><body><p>HRIS payslip</p></body></html>")
    assert pdf.startswith(b"%PDF")
