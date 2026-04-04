from __future__ import annotations

from typing import Any

import requests

# This default points the Streamlit app at the local FastAPI backend during development.
DEFAULT_BACKEND_URL = "http://localhost:8000"


class BackendApiError(Exception):
    # This custom error type keeps backend request failures easy for the UI to handle cleanly.
    pass


def get_health(base_url: str = DEFAULT_BACKEND_URL) -> dict[str, Any]:
    # This requests backend status so the UI can warn the user when the API is down.
    response = requests.get(
        f"{base_url}/health",
        timeout=10,
    )

    # This raises a clear error when the backend returns a non-success response.
    _raise_for_error(response)

    # This returns the parsed health payload for banners and status badges.
    return response.json()


def ingest_documents(
    uploaded_files: list[Any],
    base_url: str = DEFAULT_BACKEND_URL,
) -> dict[str, Any]:
    # This fails fast when the user clicks ingest without selecting any documents.
    if not uploaded_files:
        # This keeps the caller error explicit so the UI can show a friendly message.
        raise BackendApiError("Select at least one document before ingesting.")

    # This builds the multipart payload so FastAPI can receive all files in one request.
    files_payload = []

    # This walks each uploaded file so it can be forwarded to the backend unchanged.
    for uploaded_file in uploaded_files:
        # This reads the file bytes once so requests can send them in the multipart body.
        file_bytes = uploaded_file.getvalue()
        # This preserves the original filename and MIME type for backend validation.
        files_payload.append(
            (
                "files",
                (
                    uploaded_file.name,
                    file_bytes,
                    uploaded_file.type or "application/octet-stream",
                ),
            )
        )

    # This sends the selected files to the backend so the knowledge base can be rebuilt.
    response = requests.post(
        f"{base_url}/ingest",
        files=files_payload,
        timeout=120,
    )

    # This raises a clean error when the backend rejects or fails the ingest request.
    _raise_for_error(response)

    # This returns document and chunk counts so the UI can show ingestion status.
    return response.json()


def generate_brief(role: str, base_url: str = DEFAULT_BACKEND_URL) -> dict[str, Any]:
    # This posts the selected role to Agent 1 so the backend can generate a role brief.
    response = requests.post(
        f"{base_url}/brief",
        json={"role": role},
        timeout=120,
    )

    # This raises a clean error when the backend cannot generate the requested brief.
    _raise_for_error(response)

    # This returns the structured brief payload for card rendering in Streamlit.
    return response.json()


def search_knowledge(
    role: str,
    question: str,
    base_url: str = DEFAULT_BACKEND_URL,
) -> dict[str, Any]:
    # This posts the chat question and role so Agent 2 can answer within role boundaries.
    response = requests.post(
        f"{base_url}/search",
        json={
            "role": role,
            "question": question,
        },
        timeout=120,
    )

    # This raises a clean error when the backend cannot answer the request.
    _raise_for_error(response)

    # This returns the answer plus citation metadata for the chat UI.
    return response.json()


def _raise_for_error(response: requests.Response) -> None:
    # This returns immediately when the backend response succeeded.
    if response.ok:
        # This exits because there is no error to convert.
        return

    try:
        # This attempts to read a structured API error message from the backend.
        payload = response.json()
    except ValueError:
        # This falls back to the raw response body when the server did not return JSON.
        payload = {"detail": response.text}

    # This extracts the backend detail message so the UI can show something user-friendly.
    detail_message = payload.get("detail", "request failed")

    # This raises a domain-specific error so the frontend can catch one predictable exception type.
    raise BackendApiError(str(detail_message))
