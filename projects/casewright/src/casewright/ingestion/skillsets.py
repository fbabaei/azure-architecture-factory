"""Skillsets for the three indexer paths.

- multimodal: OCR + image captioning + text merge, chunk, embed, with index projections and a
  knowledge store for extracted images.
- markdown: split on markdown structure, chunk, embed.
- json: documents already structured; embed the content field directly.

All embedding skills draw their model deployment and dimensions from settings.
"""
from __future__ import annotations

import logging

from casewright.core.clients import get_search_indexer_client
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)

MULTIMODAL_SKILLSET = "casewright-multimodal-skillset"
MARKDOWN_SKILLSET = "casewright-markdown-skillset"
JSON_SKILLSET = "casewright-json-skillset"


def _embedding_skill(context: str, input_name: str):
    from azure.search.documents.indexes.models import (
        AzureOpenAIEmbeddingSkill,
        InputFieldMappingEntry,
        OutputFieldMappingEntry,
    )

    s = get_settings()
    return AzureOpenAIEmbeddingSkill(
        context=context,
        resource_url=s.openai_endpoint,
        deployment_name=s.embedding_deployment,
        model_name=s.embedding_deployment,
        dimensions=s.embedding_dimensions,
        inputs=[InputFieldMappingEntry(name="text", source=input_name)],
        outputs=[OutputFieldMappingEntry(name="embedding", target_name="content_embedding")],
    )


def _split_skill(context: str, input_name: str):
    from azure.search.documents.indexes.models import (
        InputFieldMappingEntry,
        OutputFieldMappingEntry,
        SplitSkill,
    )

    s = get_settings()
    return SplitSkill(
        context=context,
        text_split_mode="pages",
        maximum_page_length=s.chunk_size,
        page_overlap_length=s.chunk_overlap,
        inputs=[InputFieldMappingEntry(name="text", source=input_name)],
        outputs=[OutputFieldMappingEntry(name="textItems", target_name="chunks")],
    )


def _index_projection():
    from azure.search.documents.indexes.models import (
        InputFieldMappingEntry,
        SearchIndexerIndexProjection,
        SearchIndexerIndexProjectionSelector,
        SearchIndexerIndexProjectionsParameters,
        IndexProjectionMode,
    )

    s = get_settings()
    return SearchIndexerIndexProjection(
        selectors=[
            SearchIndexerIndexProjectionSelector(
                target_index_name=s.search_index_name,
                parent_key_field_name="parent_id",
                source_context="/document/chunks/*",
                mappings=[
                    InputFieldMappingEntry(name="content_text", source="/document/chunks/*"),
                    InputFieldMappingEntry(name="content_embedding", source="/document/chunks/*/content_embedding"),
                    InputFieldMappingEntry(name="document_title", source="/document/metadata_storage_name"),
                    InputFieldMappingEntry(name="source_path", source="/document/metadata_storage_path"),
                ],
            )
        ],
        parameters=SearchIndexerIndexProjectionsParameters(
            projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
        ),
    )


def ensure_skillsets() -> None:
    from azure.search.documents.indexes.models import (
        InputFieldMappingEntry,
        OcrSkill,
        OutputFieldMappingEntry,
        SearchIndexerSkillset,
    )

    client = get_search_indexer_client()
    projection = _index_projection()

    # Multimodal: OCR then split then embed.
    ocr = OcrSkill(
        context="/document/normalized_images/*",
        inputs=[InputFieldMappingEntry(name="image", source="/document/normalized_images/*")],
        outputs=[OutputFieldMappingEntry(name="text", target_name="ocr_text")],
    )
    multimodal = SearchIndexerSkillset(
        name=MULTIMODAL_SKILLSET,
        skills=[
            ocr,
            _split_skill("/document", "/document/content"),
            _embedding_skill("/document/chunks/*", "/document/chunks/*"),
        ],
        index_projection=projection,
    )

    markdown = SearchIndexerSkillset(
        name=MARKDOWN_SKILLSET,
        skills=[
            _split_skill("/document", "/document/content"),
            _embedding_skill("/document/chunks/*", "/document/chunks/*"),
        ],
        index_projection=projection,
    )

    json_skillset = SearchIndexerSkillset(
        name=JSON_SKILLSET,
        skills=[_embedding_skill("/document", "/document/content")],
        index_projection=projection,
    )

    for skillset in (multimodal, markdown, json_skillset):
        client.create_or_update_skillset(skillset)
        logger.info("ensured skillset %s", skillset.name)
