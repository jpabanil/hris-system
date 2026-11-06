"""Sandboxed Jinja templates rendered to PDF, with a public verification code."""

from __future__ import annotations

import base64
import io
import os
import secrets
import sys
from typing import Any

import qrcode
from jinja2.sandbox import SandboxedEnvironment

from app.core.actor import Actor
from app.core.config import get_settings
from app.core.errors import AppError
from app.shared.files import save_upload
from app.shared.models import DocumentTemplate, GeneratedDocument
from app.shared.sequences import next_number

_env = SandboxedEnvironment(autoescape=True)


def render_body(body: str, merge: dict[str, Any]) -> str:
    try:
        return _env.from_string(body).render(**merge)
    except Exception as exc:
        raise AppError("template_error", "The template could not be rendered", 400) from exc


def _macos_pdf_libs() -> None:
    """Homebrew pango is not on the default dyld path. Set it before WeasyPrint loads."""
    if sys.platform != "darwin":
        return
    lib = "/opt/homebrew/lib"
    if not os.path.isdir(lib):
        return
    current = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    parts = [part for part in current.split(":") if part]
    if lib not in parts:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join([lib, *parts])


def html_to_pdf(html: str) -> bytes:
    _macos_pdf_libs()
    try:
        from weasyprint import HTML
    except OSError as exc:
        raise AppError(
            "pdf_unavailable",
            "PDF rendering needs the WeasyPrint system libraries (pango).",
            500,
        ) from exc
    return HTML(string=html).write_pdf()


def protect_pdf(pdf: bytes, password: str) -> bytes:
    import pikepdf

    source = pikepdf.open(io.BytesIO(pdf))
    output = io.BytesIO()
    source.save(output, encryption=pikepdf.Encryption(owner=password, user=password))
    return output.getvalue()


async def generate_document(
    actor: Actor,
    *,
    doc_type: str,
    merge: dict[str, Any],
    employee_id: str | None,
    template_body: str | None = None,
) -> GeneratedDocument:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    template = await DocumentTemplate.find_one(
        {"company_id": actor.company_id, "type": doc_type, "is_active": True, "deleted_at": None}
    )
    body = template_body or (template.body if template else None)
    if not body:
        body = (
            "<h1>{{ doc_type }}</h1><p>{{ employee.full_name }}</p>"
            "<p>{{ sequence_no }}</p><p>{{ verification_url }}</p>"
        )
    code = secrets.token_urlsafe(8)
    sequence = await next_number(actor.company_id, f"doc-{doc_type}", f"{doc_type[:3].upper()}-")
    url = f"{get_settings().public_base_url}/verify/{code}"
    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    merge = {
        **merge,
        "doc_type": doc_type,
        "sequence_no": sequence,
        "verification_url": url,
    }
    html = render_body(body, merge)
    pdf = html_to_pdf(
        f"<html><body>{html}<p><img alt='QR' "
        f"src='data:image/png;base64,{encoded}'/></p></body></html>"
    )
    stored = await save_upload(
        actor,
        filename=f"{sequence}.pdf",
        content_type="application/pdf",
        data=pdf,
    )
    generated = GeneratedDocument(
        company_id=actor.company_id,
        template_id=str(template.id) if template else None,
        employee_id=employee_id,
        doc_type=doc_type,
        file_key=stored.key,
        verification_code=code,
        sequence_no=sequence,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await generated.insert()
    return generated
