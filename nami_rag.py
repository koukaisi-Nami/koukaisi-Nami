"""Scoped hosted-RAG adapter for Nami.

OpenAI File Search is used only through vector stores selected by Nami's scope
policy. Uploaded source files expire after 30 days by default to bound storage.
No database access lives here; app.py remains responsible for scope mapping.
"""
from __future__ import annotations

import io
import re
from typing import Iterable

FILES_URL = "https://api.openai.com/v1/files"
VECTOR_STORES_URL = "https://api.openai.com/v1/vector_stores"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
FILE_TTL_SECONDS = 30 * 24 * 60 * 60


def _headers(api_key: str) -> dict:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")
    return {"Authorization": f"Bearer {api_key}"}


def safe_name(value: str, fallback: str = "document.pdf") -> str:
    name = re.sub(r"[^0-9A-Za-z._\-ぁ-んァ-ヶ一-龠]+", "_", value or "").strip("._")
    return (name or fallback)[:180]


def create_vector_store(name: str, api_key: str, http) -> str:
    r = http.post(
        VECTOR_STORES_URL,
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json={"name": safe_name(name, "nami-knowledge")[:120]},
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"vector store create failed {r.status_code}: {r.text[:500]}")
    store_id = str((r.json() or {}).get("id") or "")
    if not store_id.startswith("vs_"):
        raise RuntimeError("vector store create returned no id")
    return store_id


def upload_file(blob: bytes, filename: str, api_key: str, http) -> str:
    if not blob:
        raise RuntimeError("empty file")
    if len(blob) > MAX_UPLOAD_BYTES:
        raise RuntimeError("file too large for Nami knowledge indexing")
    files = {"file": (safe_name(filename), io.BytesIO(blob), "application/pdf")}
    data = {
        "purpose": "assistants",
        "expires_after[anchor]": "created_at",
        "expires_after[seconds]": str(FILE_TTL_SECONDS),
    }
    r = http.post(FILES_URL, headers=_headers(api_key), files=files, data=data, timeout=90)
    if not r.ok:
        raise RuntimeError(f"file upload failed {r.status_code}: {r.text[:500]}")
    file_id = str((r.json() or {}).get("id") or "")
    if not file_id.startswith("file-"):
        raise RuntimeError("file upload returned no id")
    return file_id


def attach_file(vector_store_id: str, file_id: str, api_key: str, http, attributes=None) -> str:
    body = {"file_id": file_id}
    if attributes:
        body["attributes"] = dict(attributes)
    r = http.post(
        f"{VECTOR_STORES_URL}/{vector_store_id}/files",
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json=body,
        timeout=45,
    )
    if not r.ok:
        raise RuntimeError(f"vector attach failed {r.status_code}: {r.text[:500]}")
    payload = r.json() or {}
    return str(payload.get("id") or file_id)


def index_pdf(blob: bytes, filename: str, vector_store_id: str, api_key: str, http, attributes=None) -> tuple[str, str]:
    file_id = upload_file(blob, filename, api_key, http)
    attached_id = attach_file(vector_store_id, file_id, api_key, http, attributes=attributes)
    return file_id, attached_id


def file_search_tool(vector_store_ids: Iterable[str], max_results: int = 4) -> dict | None:
    ids = []
    for value in vector_store_ids or ():
        value = str(value or "").strip()
        if value.startswith("vs_") and value not in ids:
            ids.append(value)
    if not ids:
        return None
    return {
        "type": "file_search",
        "vector_store_ids": ids[:3],
        "max_num_results": max(1, min(8, int(max_results))),
    }
