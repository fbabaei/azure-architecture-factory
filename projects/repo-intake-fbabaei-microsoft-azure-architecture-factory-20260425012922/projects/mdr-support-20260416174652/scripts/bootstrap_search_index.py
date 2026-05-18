"""Create and optionally seed a hybrid Azure AI Search index for MDR Q&A."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Iterable
from urllib import request as urllib_request

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "sample-corpus"
DEFAULT_MANIFEST_PATH = DEFAULT_SOURCE_DIR / "manifest.json"
DEFAULT_INDEX_NAME = "compliance-knowledge-base"
DEFAULT_EMBEDDINGS_DEPLOYMENT = "text-embedding-3-small"
DEFAULT_OPENAI_API_VERSION = "2024-10-21"
SUPPORTED_SOURCE_SUFFIXES = {".md", ".txt"}


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    title: str
    source: str
    category: str


def _search_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
        return headers
    token = DefaultAzureCredential().get_token("https://search.azure.com/.default")
    headers["Authorization"] = f"Bearer {token.token}"
    return headers


def _create_openai_client(*, openai_endpoint: str, api_version: str) -> AzureOpenAI:
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=openai_endpoint,
        api_version=api_version,
        azure_ad_token_provider=token_provider,
    )


def _chunk_text(text: str, *, words_per_chunk: int = 700, overlap: int = 100) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    step = max(words_per_chunk - overlap, 1)
    start = 0
    while start < len(words):
        chunks.append(" ".join(words[start : start + words_per_chunk]))
        start += step
    return chunks


def _index_schema(index_name: str) -> dict[str, object]:
    return {
        "name": index_name,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True, "searchable": False},
            {"name": "title", "type": "Edm.String", "searchable": True},
            {"name": "content", "type": "Edm.String", "searchable": True},
            {"name": "source", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "category", "type": "Edm.String", "searchable": True, "filterable": True, "facetable": True},
            {
                "name": "contentVector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "dimensions": 1536,
                "vectorSearchProfile": "mdr-vector-profile",
            },
        ],
        "vectorSearch": {
            "algorithms": [
                {
                    "name": "mdr-hnsw",
                    "kind": "hnsw",
                    "hnswParameters": {"metric": "cosine"},
                }
            ],
            "profiles": [{"name": "mdr-vector-profile", "algorithm": "mdr-hnsw"}],
        },
        "semantic": {
            "configurations": [
                {
                    "name": "default",
                    "prioritizedFields": {
                        "titleField": {"fieldName": "title"},
                        "prioritizedContentFields": [{"fieldName": "content"}],
                    },
                }
            ]
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the MDR Azure AI Search index and optionally seed a source corpus.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help=(
            "Directory containing .md/.txt source files. Defaults to the in-project "
            "sample corpus when --create-only is not used."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Optional JSON manifest describing corpus files, titles, and categories.",
    )
    parser.add_argument(
        "--search-endpoint",
        default="",
        help="Azure AI Search endpoint. Falls back to AZURE_AI_SEARCH_ENDPOINT.",
    )
    parser.add_argument(
        "--index-name",
        default="",
        help=(
            "Azure AI Search index name. Falls back to AZURE_AI_SEARCH_INDEX_NAME "
            f"or {DEFAULT_INDEX_NAME}."
        ),
    )
    parser.add_argument(
        "--search-api-key",
        default="",
        help="Optional Azure AI Search admin key. Falls back to AZURE_AI_SEARCH_API_KEY.",
    )
    parser.add_argument(
        "--openai-endpoint",
        default="",
        help="Azure OpenAI endpoint. Falls back to AZURE_OPENAI_ENDPOINT.",
    )
    parser.add_argument(
        "--openai-api-version",
        default="",
        help=(
            "Azure OpenAI API version. Falls back to AZURE_OPENAI_API_VERSION "
            f"or {DEFAULT_OPENAI_API_VERSION}."
        ),
    )
    parser.add_argument(
        "--embeddings-deployment",
        default="",
        help=(
            "Azure OpenAI embeddings deployment. Falls back to "
            f"AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT or {DEFAULT_EMBEDDINGS_DEPLOYMENT}."
        ),
    )
    parser.add_argument(
        "--default-category",
        default="mdr-reference",
        help="Fallback category applied when a manifest entry does not specify one.",
    )
    parser.add_argument(
        "--create-only",
        action="store_true",
        help="Create or update the index schema without uploading any documents.",
    )
    return parser.parse_args()


def _require_setting(value: str, *, arg_name: str, env_var: str) -> str:
    if value:
        return value
    raise SystemExit(f"Missing {arg_name}. Provide {arg_name} or set {env_var}.")


def _resolve_optional_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _resolve_source_dir(source_dir: Path | None, *, create_only: bool) -> Path | None:
    resolved = _resolve_optional_path(source_dir)
    if resolved is None and not create_only:
        resolved = DEFAULT_SOURCE_DIR.resolve()
    if resolved is None:
        return None
    if not resolved.exists() or not resolved.is_dir():
        raise SystemExit(f"Source directory does not exist: {resolved}")
    return resolved


def _resolve_manifest_path(manifest_path: Path | None, source_dir: Path | None) -> Path | None:
    resolved = _resolve_optional_path(manifest_path)
    if resolved is not None:
        if not resolved.exists() or not resolved.is_file():
            raise SystemExit(f"Manifest file does not exist: {resolved}")
        return resolved
    if source_dir is None:
        return None
    candidate = source_dir / "manifest.json"
    return candidate if candidate.exists() and candidate.is_file() else None


def _source_document_from_path(path: Path, source_dir: Path, *, category: str) -> SourceDocument:
    return SourceDocument(
        path=path,
        title=path.stem.replace("-", " "),
        source=str(path.relative_to(source_dir)),
        category=category,
    )


def load_manifest(manifest_path: Path, source_dir: Path, *, default_category: str) -> list[SourceDocument]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise SystemExit(f"Manifest must contain a non-empty 'documents' list: {manifest_path}")

    resolved: list[SourceDocument] = []
    for entry in documents:
        if not isinstance(entry, dict):
            raise SystemExit(f"Manifest entries must be JSON objects: {manifest_path}")
        relative_path = entry.get("path")
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise SystemExit(f"Manifest entries must include a non-empty 'path': {manifest_path}")
        path = (source_dir / relative_path).resolve()
        if not path.exists() or not path.is_file():
            raise SystemExit(f"Manifest path does not exist: {path}")
        if path.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
            raise SystemExit(f"Unsupported manifest file type: {path}")
        resolved.append(
            SourceDocument(
                path=path,
                title=str(entry.get("title") or path.stem.replace("-", " ")),
                source=relative_path.replace("\\", "/"),
                category=str(entry.get("category") or default_category),
            )
        )
    return resolved


def _iter_source_files(source_dir: Path) -> Iterable[Path]:
    for path in source_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SOURCE_SUFFIXES:
            yield path


def build_source_documents(
    source_dir: Path | None,
    *,
    manifest_path: Path | None,
    default_category: str,
) -> list[SourceDocument]:
    if source_dir is None:
        return []
    if manifest_path is not None:
        return load_manifest(manifest_path, source_dir, default_category=default_category)
    return [
        _source_document_from_path(path, source_dir, category=default_category)
        for path in sorted(_iter_source_files(source_dir))
    ]


def _upsert_index(search_endpoint: str, index_name: str, headers: dict[str, str]) -> None:
    url = f"{search_endpoint.rstrip('/')}/indexes/{index_name}?api-version=2024-07-01"
    req = urllib_request.Request(
        url,
        data=json.dumps(_index_schema(index_name)).encode("utf-8"),
        headers=headers,
        method="PUT",
    )
    with urllib_request.urlopen(req, timeout=30) as response:
        print(f"Index upserted: {response.status}")


def _upload_documents(
    *,
    search_endpoint: str,
    index_name: str,
    headers: dict[str, str],
    documents: list[SourceDocument],
    openai_endpoint: str,
    openai_api_version: str,
    embeddings_deployment: str,
) -> None:
    client = _create_openai_client(
        openai_endpoint=openai_endpoint,
        api_version=openai_api_version,
    )
    actions: list[dict[str, object]] = []
    for document in documents:
        text = document.path.read_text(encoding="utf-8")
        for idx, chunk in enumerate(_chunk_text(text)):
            embedding = client.embeddings.create(
                model=embeddings_deployment,
                input=chunk,
            ).data[0].embedding
            actions.append(
                {
                    "@search.action": "mergeOrUpload",
                    "id": f"{document.path.stem}-{idx}",
                    "title": document.title,
                    "content": chunk,
                    "source": document.source,
                    "category": document.category,
                    "contentVector": embedding,
                }
            )

    if not actions:
        print("No source documents found to upload.")
        return

    url = f"{search_endpoint.rstrip('/')}/indexes/{index_name}/docs/index?api-version=2024-07-01"
    req = urllib_request.Request(
        url,
        data=json.dumps({"value": actions}).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=60) as response:
        print(f"Uploaded {len(actions)} chunks: {response.status}")


def main() -> None:
    args = _parse_args()

    source_dir = _resolve_source_dir(args.source_dir, create_only=args.create_only)
    manifest_path = _resolve_manifest_path(args.manifest, source_dir)
    documents = build_source_documents(
        source_dir,
        manifest_path=manifest_path,
        default_category=args.default_category,
    )

    search_endpoint = _require_setting(
        args.search_endpoint or os.getenv("AZURE_AI_SEARCH_ENDPOINT", ""),
        arg_name="--search-endpoint",
        env_var="AZURE_AI_SEARCH_ENDPOINT",
    )
    index_name = args.index_name or os.getenv("AZURE_AI_SEARCH_INDEX_NAME", DEFAULT_INDEX_NAME)
    api_key = args.search_api_key or os.getenv("AZURE_AI_SEARCH_API_KEY", "")
    embeddings_deployment = args.embeddings_deployment or os.getenv(
        "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT",
        DEFAULT_EMBEDDINGS_DEPLOYMENT,
    )
    openai_api_version = args.openai_api_version or os.getenv(
        "AZURE_OPENAI_API_VERSION",
        DEFAULT_OPENAI_API_VERSION,
    )

    headers = _search_headers(api_key)
    _upsert_index(search_endpoint, index_name, headers)
    if not args.create_only and documents:
        openai_endpoint = _require_setting(
            args.openai_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            arg_name="--openai-endpoint",
            env_var="AZURE_OPENAI_ENDPOINT",
        )
        _upload_documents(
            search_endpoint=search_endpoint,
            index_name=index_name,
            headers=headers,
            documents=documents,
            openai_endpoint=openai_endpoint,
            openai_api_version=openai_api_version,
            embeddings_deployment=embeddings_deployment,
        )
    elif not args.create_only:
        print("No source documents found to upload.")


if __name__ == "__main__":
    main()