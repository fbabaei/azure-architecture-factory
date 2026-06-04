"""Skillsets for the three indexer paths.

- multimodal: Document Intelligence layout-aware extraction of text sections and images, text-chunk
  embeddings, GPT-vision image verbalization, image-description embeddings, and a knowledge store
  for extracted images — projected into the index via separate text/image selectors.
- markdown: split on markdown structure, chunk, embed.
- json: documents already structured; embed the content field directly.

All embedding skills draw their model deployment and dimensions from settings. Every external
call (Search, Azure OpenAI, AI Services, storage knowledge store) authenticates with the search
service's managed identity — no keys or connection secrets are embedded here.
"""
from __future__ import annotations

import logging

from casewright.core.clients import get_search_indexer_client
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)

MULTIMODAL_SKILLSET = "casewright-multimodal-skillset"
MARKDOWN_SKILLSET = "casewright-markdown-skillset"
JSON_SKILLSET = "casewright-json-skillset"

# System prompt steering GPT-vision image verbalization during ingestion.
IMAGE_VERBALIZATION_SYSTEM_MESSAGE = (
    "You are an AI assistant that describes images in detail for search indexing. "
    "Describe the visual content, text, charts, diagrams, and any other relevant "
    "information present in the image. Be concise but comprehensive."
)


def _as_search_string_literal(text: str) -> str:
    """Format a string as an Azure AI Search skill input string literal (='...', '' escapes)."""
    escaped = text.replace("'", "''")
    return f"='{escaped}'"


def _chat_completion_uri() -> str:
    """Full Azure OpenAI chat-completions URL for the vision deployment used by the image skill."""
    s = get_settings()
    endpoint = s.openai_endpoint.rstrip("/")
    return f"{endpoint}/openai/deployments/{s.chat_deployment}/chat/completions?api-version=2025-01-01-preview"


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


def _build_multimodal_skillset():
    """Layout-aware multimodal skillset.

    Pipeline: Document Intelligence layout extraction -> text-chunk embeddings -> (optional)
    GPT-vision image verbalization -> image-description embeddings -> image-path shaper. Text and
    image enrichments are projected into the index via separate selectors, and extracted images are
    persisted to a knowledge store. AI Services + storage authenticate via the search service's
    managed identity (no keys/connection strings).
    """
    from azure.search.documents.indexes.models import (
        AIServicesAccountIdentity,
        AzureOpenAIEmbeddingSkill,
        ChatCompletionSkill,
        DocumentIntelligenceLayoutSkill,
        DocumentIntelligenceLayoutSkillChunkingProperties,
        IndexProjectionMode,
        InputFieldMappingEntry,
        OutputFieldMappingEntry,
        SearchIndexerIndexProjection,
        SearchIndexerIndexProjectionSelector,
        SearchIndexerIndexProjectionsParameters,
        SearchIndexerKnowledgeStore,
        SearchIndexerKnowledgeStoreObjectProjectionSelector,
        SearchIndexerKnowledgeStoreProjection,
        SearchIndexerSkillset,
        ShaperSkill,
    )

    s = get_settings()
    images_container = s.knowledge_store_container
    verbalize = s.image_verbalization_enabled

    skills: list = [
        DocumentIntelligenceLayoutSkill(
            name="document-intelligence-layout-skill",
            description="Extract text sections and images with layout metadata via Document Intelligence",
            context="/document",
            output_mode="oneToMany",
            output_format="text",
            markdown_header_depth=None,  # type: ignore[arg-type]
            extraction_options=["images", "locationMetadata"],
            chunking_properties=DocumentIntelligenceLayoutSkillChunkingProperties(
                unit="characters",
                maximum_length=s.chunk_size,
                overlap_length=s.chunk_overlap,
            ),
            inputs=[InputFieldMappingEntry(name="file_data", source="/document/file_data")],
            outputs=[
                OutputFieldMappingEntry(name="text_sections", target_name="text_sections"),
                OutputFieldMappingEntry(name="normalized_images", target_name="normalized_images"),
            ],
        ),
        AzureOpenAIEmbeddingSkill(
            name="text-chunk-embedding-skill",
            description="Embed text chunks using Azure OpenAI",
            context="/document/text_sections/*",
            resource_url=s.openai_endpoint,
            deployment_name=s.embedding_deployment,
            model_name=s.embedding_deployment,
            dimensions=s.embedding_dimensions,
            inputs=[InputFieldMappingEntry(name="text", source="/document/text_sections/*/content")],
            outputs=[OutputFieldMappingEntry(name="embedding", target_name="text_vector")],
        ),
    ]

    if verbalize:
        skills.extend(
            [
                ChatCompletionSkill(
                    name="image-verbalization-skill",
                    description="Describe extracted images using a GPT vision deployment",
                    context="/document/normalized_images/*",
                    uri=_chat_completion_uri(),
                    inputs=[
                        InputFieldMappingEntry(
                            name="systemMessage",
                            source=_as_search_string_literal(IMAGE_VERBALIZATION_SYSTEM_MESSAGE),
                        ),
                        InputFieldMappingEntry(name="userMessage", source="='Please describe this image.'"),
                        InputFieldMappingEntry(name="image", source="/document/normalized_images/*/data"),
                    ],
                    outputs=[OutputFieldMappingEntry(name="response", target_name="verbalizedImage")],
                ),
                AzureOpenAIEmbeddingSkill(
                    name="image-description-embedding-skill",
                    description="Embed image descriptions using Azure OpenAI",
                    context="/document/normalized_images/*",
                    resource_url=s.openai_endpoint,
                    deployment_name=s.embedding_deployment,
                    model_name=s.embedding_deployment,
                    dimensions=s.embedding_dimensions,
                    inputs=[
                        InputFieldMappingEntry(
                            name="text", source="/document/normalized_images/*/verbalizedImage"
                        )
                    ],
                    outputs=[OutputFieldMappingEntry(name="embedding", target_name="verbalizedImage_vector")],
                ),
                ShaperSkill(
                    name="image-path-shaper-skill",
                    context="/document/normalized_images/*",
                    inputs=[
                        InputFieldMappingEntry(
                            name="normalized_images", source="/document/normalized_images/*"
                        ),
                        InputFieldMappingEntry(
                            name="imagePath",
                            source=f"='{images_container}/'+$(/document/normalized_images/*/imagePath)",
                        ),
                    ],
                    outputs=[OutputFieldMappingEntry(name="output", target_name="new_normalized_images")],
                ),
            ]
        )

    selectors = [
        SearchIndexerIndexProjectionSelector(
            target_index_name=s.search_index_name,
            parent_key_field_name="text_document_id",
            source_context="/document/text_sections/*",
            mappings=[
                InputFieldMappingEntry(name="content_text", source="/document/text_sections/*/content"),
                InputFieldMappingEntry(
                    name="content_embedding", source="/document/text_sections/*/text_vector"
                ),
                InputFieldMappingEntry(
                    name="location_metadata", source="/document/text_sections/*/locationMetadata"
                ),
                InputFieldMappingEntry(name="document_title", source="/document/metadata_storage_name"),
                InputFieldMappingEntry(name="source_path", source="/document/metadata_storage_path"),
            ],
        ),
    ]

    if verbalize:
        selectors.append(
            SearchIndexerIndexProjectionSelector(
                target_index_name=s.search_index_name,
                parent_key_field_name="image_document_id",
                source_context="/document/normalized_images/*",
                mappings=[
                    InputFieldMappingEntry(
                        name="content_text", source="/document/normalized_images/*/verbalizedImage"
                    ),
                    InputFieldMappingEntry(
                        name="content_embedding",
                        source="/document/normalized_images/*/verbalizedImage_vector",
                    ),
                    InputFieldMappingEntry(
                        name="content_path",
                        source="/document/normalized_images/*/new_normalized_images/imagePath",
                    ),
                    InputFieldMappingEntry(
                        name="location_metadata", source="/document/normalized_images/*/locationMetadata"
                    ),
                    InputFieldMappingEntry(name="document_title", source="/document/metadata_storage_name"),
                    InputFieldMappingEntry(name="source_path", source="/document/metadata_storage_path"),
                ],
            )
        )

    index_projection = SearchIndexerIndexProjection(
        selectors=selectors,
        parameters=SearchIndexerIndexProjectionsParameters(
            projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
        ),
    )

    knowledge_store = None
    if verbalize and s.storage_resource_id:
        knowledge_store = SearchIndexerKnowledgeStore(
            storage_connection_string=f"ResourceId={s.storage_resource_id}",
            projections=[
                SearchIndexerKnowledgeStoreProjection(
                    objects=[
                        SearchIndexerKnowledgeStoreObjectProjectionSelector(
                            storage_container=images_container,
                            source="/document/normalized_images/*",
                        )
                    ]
                )
            ],
        )

    cognitive_services_account = None
    if s.ai_services_endpoint:
        cognitive_services_account = AIServicesAccountIdentity(
            subdomain_url=s.ai_services_endpoint.rstrip("/")
        )

    return SearchIndexerSkillset(
        name=MULTIMODAL_SKILLSET,
        description="Multimodal document processing: layout extraction, text + image embeddings",
        skills=skills,
        index_projection=index_projection,
        knowledge_store=knowledge_store,
        cognitive_services_account=cognitive_services_account,
    )


def ensure_skillsets() -> None:
    from azure.search.documents.indexes.models import (
        SearchIndexerSkillset,
    )

    client = get_search_indexer_client()
    projection = _index_projection()

    multimodal = _build_multimodal_skillset()

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
