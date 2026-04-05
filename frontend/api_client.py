from __future__ import annotations

from typing import Any

import requests

DEFAULT_BACKEND_URL = "http://localhost:8000"


class BackendApiError(Exception):
    pass


def get_health(base_url: str = DEFAULT_BACKEND_URL) -> dict[str, Any]:
    response = requests.get(
        f"{base_url}/health",
        timeout=10,
    )

    _raise_for_error(response)
    return response.json()


def ingest_documents(
    uploaded_files: list[Any],
    base_url: str = DEFAULT_BACKEND_URL,
) -> dict[str, Any]:
    if not uploaded_files:
        raise BackendApiError("Select at least one document before ingesting.")

    files_payload = []

    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
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

    response = requests.post(
        f"{base_url}/ingest",
        files=files_payload,
        timeout=120,
    )

    _raise_for_error(response)
    return response.json()


def generate_brief(role: str, base_url: str = DEFAULT_BACKEND_URL) -> dict[str, Any]:
    response = requests.post(
        f"{base_url}/brief",
        json={"role": role},
        timeout=120,
    )

    _raise_for_error(response)
    return response.json()


def search_knowledge(
    role: str,
    question: str,
    base_url: str = DEFAULT_BACKEND_URL,
) -> dict[str, Any]:
    response = requests.post(
        f"{base_url}/search",
        json={
            "role": role,
            "question": question,
        },
        timeout=120,
    )

    _raise_for_error(response)
    return response.json()


def _raise_for_error(response: requests.Response) -> None:
    if response.ok:
        return

    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": response.text}

    detail_message = payload.get("detail", "request failed")
    raise BackendApiError(str(detail_message))
