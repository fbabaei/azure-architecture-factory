"""Create and optionally seed a hybrid Azure AI Search index for MDR Q&A."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable
from urllib import request as urllib_request

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI


def _search_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
        return headers
    token = DefaultAzureCredential().get_token("https://search.azure.com/.default")
    headers["Authorization"] = f"Bearer {token.token}"
    return headers


def _create_openai_client() -> AzureOpenAI:
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
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


def _iter_source_files(source_dir: Path) -> Iterable[Path]:
    for path in source_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            yield path


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
    source_dir: Path,
    embeddings_deployment: str,
) -> None:
    client = _create_openai_client()
    actions: list[dict[str, object]] = []
    for path in _iter_source_files(source_dir):
        text = path.read_text(encoding="utf-8")
        for idx, chunk in enumerate(_chunk_text(text)):
            embedding = client.embeddings.create(
                model=embeddings_deployment,
                input=chunk,
            ).data[0].embedding
            actions.append(
                {
                    "@search.action": "mergeOrUpload",
                    "id": f"{path.stem}-{idx}",
                    "title": path.stem.replace("-", " "),
                    "content": chunk,
                    "source": str(path.relative_to(source_dir)),
                    "category": "mdr-reference",
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()

    search_endpoint = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME", "compliance-knowledge-base")
    api_key = os.getenv("AZURE_AI_SEARCH_API_KEY", "")
    embeddings_deployment = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "text-embedding-3-small")

    headers = _search_headers(api_key)
    _upsert_index(search_endpoint, index_name, headers)
    if args.source_dir:
        _upload_documents(
            search_endpoint=search_endpoint,
            index_name=index_name,
            headers=headers,
            source_dir=args.source_dir,
            embeddings_deployment=embeddings_deployment,
        )


if __name__ == "__main__":
    main()