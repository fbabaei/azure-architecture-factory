# Azure AI Agent Foundry Learning Paths

Use this guide to follow the Azure AI Agent Foundry learning tracks in a practical order. Each track starts with the `/learn-ai-capability` prompt, points to the relevant source material, and ends with an application follow-up.

## How Assistant Agents Help Through This Guide

Use Azure AI Learning Orchestrator as the main step-by-step assistant for learning tracks. It should walk through one learning step at a time, point to the source path, define the checkpoint, and wait for the user before moving on.

Recommended starter prompt:

```text
Azure AI Learning Orchestrator, walk me through this learning path one step at a time. For each step, give me the source path, goal, action, checkpoint, and next prompt to use. Wait for my checkpoint before continuing.
```

When the user moves from learning to a real app, use Azure AI Application Orchestrator for the design and Application Planning Companion Agent to manage the application steps. Use Application Implementation Validation Agent only when an approved step needs file changes, terminal commands, tests, local servers, or validation evidence.

## Overall Order

1. Azure AI Services foundations
2. Vision solutions
3. NLP solutions
4. Knowledge mining and Azure AI Search
5. Document Intelligence
6. Generative AI and Azure OpenAI
7. Apply what you learned with app blueprints

This order works because later tracks assume you understand Azure resources, endpoints, keys, authentication, SDK usage, cleanup, and cost.

## 1. Azure AI Services Foundations

Goal: understand how Azure AI Services are provisioned, secured, monitored, and used.

Use this prompt in VS Code Chat:

```text
/learn-ai-capability Help me learn Azure AI Services foundations.
```

Steps:

1. Read the foundations module under `external/Azure-AI-Engineer-Associate-Notes/1 - Get started with Azure AI Services`.
2. Learn the resource model: single-service resources vs. multi-service Azure AI Services resources.
3. Learn authentication options: keys, endpoints, Microsoft Entra ID, and managed identity.
4. Review responsible AI and content safety concepts.
5. Practice creating a resource in Azure, using the endpoint and key locally, then deleting the resource.
6. Ask the Azure AI Services Foundation Orchestrator for help when you need provisioning, security, monitoring, containers, or content safety guidance.

Outcome: write a short note explaining endpoint, key, region, resource group, and cleanup steps.

## 2. Vision Solutions

Goal: learn image analysis, OCR, image-aware chat, image generation, video generation, and Content Understanding.

Use this prompt in VS Code Chat:

```text
/learn-ai-capability Guide me through Azure AI Vision.
```

Steps:

1. Start with `external/Azure-AI-Engineer-Associate-Notes/2 - Create computer vision solutions with Azure AI Vision`.
2. Use the lab repo at `external/mslearn-ai-vision/Instructions/Exercises`.
3. Follow the basic image analysis and OCR material first.
4. Move to generative vision with `01-gen-ai-vision.md`.
5. Try image generation with `02-generate-image.md`.
6. Try video generation with `03-generate-video.md`.
7. Try Content Understanding with `04-content-understanding.md`.
8. Apply the learning with the Vision Chat App Agent, Image Generation App Agent, Video Generation App Agent, or Content Understanding Metadata Agent.

Application follow-up:

```text
/design-ai-agent-solution Design an image metadata extraction agent for product photos.
```

## 3. NLP Solutions

Goal: learn text analytics, translation, speech, conversational language understanding, question answering, and bot-style scenarios.

Use this prompt in VS Code Chat:

```text
/learn-ai-capability Help me learn Azure AI Language and Speech.
```

Steps:

1. Study `external/Azure-AI-Engineer-Associate-Notes/3 - Develop natural language processing solutions with Azure AI Services`.
2. Start with text analytics: language detection, key phrases, sentiment, and entities.
3. Move to translation.
4. Study speech-to-text and text-to-speech.
5. Learn conversational language understanding.
6. Review question answering and bot integration patterns.
7. Ask the NLP Solutions Orchestrator to route you to a specific subtopic when needed.

Practice task: build a small flow that takes text, extracts entities, summarizes intent, and routes to a response.

## 4. Knowledge Mining And Azure AI Search

Goal: learn indexing, skillsets, custom skills, knowledge stores, vector search, hybrid search, multimodal search, classic search, RAG grounding, and agentic retrieval.

Use this prompt in VS Code Chat:

```text
/learn-ai-capability Help me learn Azure AI Search knowledge mining.
```

Steps:

1. Ask Azure AI Search Training Agent to create a step-by-step route from the Microsoft Learn introduction and local learning notes.
2. Study `external/Azure-AI-Engineer-Associate-Notes/4 - Implement knowledge mining solutions with Azure AI Search`.
3. Learn the core objects: data source, index, indexer, and skillset.
4. Learn classic search: direct index queries, indexing, querying, filters, facets, autocomplete, synonyms, semantic ranking, relevance tuning, and security.
5. Learn how enrichment works.
6. Add custom skills conceptually.
7. Learn vector search, hybrid search, and multimodal search.
8. Learn how conventional RAG uses search results for grounding.
9. Learn agentic retrieval: knowledge bases, knowledge sources, query planning, query decomposition, semantic reranking, references, activity logs, and reasoning effort.
10. Use the Knowledge Mining Search Orchestrator for broad search routing questions.
11. Apply the learning with Classic Search App Agent, RAG Search App Agent, or Agentic Retrieval App Agent.
12. Use [Azure AI Search Agents Step By Step](azure-ai-search-agents-step-by-step.md) when you need the beginner walkthrough for choosing and using these agents.

Application follow-up:

```text
/design-ai-agent-solution Design a RAG agent for searchable internal documents.
```

```text
/design-ai-agent-solution Use the Agentic Retrieval App Agent to design an enterprise assistant over SharePoint and indexed policy documents.
```

## 5. Document Intelligence

Goal: learn prebuilt models, custom models, composed models, layout extraction, forms, invoices, and document-to-search flows.

Primary Microsoft Learn source: <https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/?view=doc-intel-4.0.0>.

Use this prompt in VS Code Chat:

```text
/learn-ai-capability Guide me through Document Intelligence custom models.
```

Steps:

1. Ask Document Intelligence Training Agent to create a step-by-step route from the Microsoft Learn landing page and local lab files.
2. Study `external/Azure-AI-Engineer-Associate-Notes/5 - Develop solutions with Azure AI Document Intelligence`.
3. Use the lab repo at `external/Azure-AI-Engineer-Associate-Notes/5 - Develop solutions with Azure AI Document Intelligence/mslearn-ai-document-intelligence`.
4. Start with the service overview, Studio concepts, resource setup, auth options, and response JSON anatomy.
5. Start with prebuilt models in `Instructions/Exercises/01-use-prebuilt-models.md` and `Labfiles/01-prebuild-models/Python/document-analysis.py`.
6. Move to custom field extraction in `Instructions/Exercises/02-custom-document-intelligence.md` and `Labfiles/02-custom-document-intelligence/Python/test-model.py`.
7. Move to composed models in `Instructions/Exercises/03-composed-model.md`.
8. Add custom classification, query fields, add-on capabilities, batch analysis, confidence scores, and responsible AI review from Microsoft Learn when those topics match your application.
9. Apply the learning with Document Extraction App Agent for structured extraction or Document Knowledge Pipeline Agent for search/RAG pipelines.
10. Use [Document Intelligence Agents Step By Step](document-intelligence-agents-step-by-step.md) when you need the beginner walkthrough for choosing and using these agents.

Application follow-up:

```text
/design-ai-agent-solution Design an agent that extracts invoice fields and lets users query the results.
```

## 6. Generative AI And Azure OpenAI

Goal: learn chat, embeddings, prompt patterns, RAG, image generation, code generation, and Foundry integration.

Use this prompt in VS Code Chat:

```text
/learn-ai-capability Help me learn Azure OpenAI and RAG.
```

Steps:

1. Study `external/Azure-AI-Engineer-Associate-Notes/6 - Develop Generative AI solutions with Azure OpenAI Service`.
2. Use `external/Azure-AI-Engineer-Associate-Notes/6 - Develop Generative AI solutions with Azure OpenAI Service/mslearn-openai`.
3. Start with app development basics.
4. Learn the Azure OpenAI API.
5. Learn prompt engineering.
6. Learn embeddings.
7. Learn use-your-own-data and RAG patterns.
8. Learn image generation if relevant.
9. Use the Generative AI Solutions Orchestrator for broad learning.
10. Use the Foundry Integration Agent for model deployments, endpoints, quotas, and project configuration.

Application follow-up:

```text
/design-ai-agent-solution Design a Foundry-backed assistant that answers questions over uploaded documents.
```

## 7. Apply With App Blueprints

After each learning track, apply the concepts with this prompt:

```text
/design-ai-agent-solution <your real app scenario>
```

Use these application blueprints:

| Blueprint | Use when |
| --- | --- |
| Vision Chat App Agent | You need image-aware question answering. |
| Image Generation App Agent | You need text-to-image app features. |
| Video Generation App Agent | You need Sora or generated video workflows. |
| Content Understanding Metadata Agent | You need searchable image metadata. |
| Classic Search App Agent | You need direct index-first Azure AI Search with filters, facets, autocomplete, relevance tuning, or semantic/vector/hybrid queries. |
| RAG Search App Agent | You need search and grounding. |
| Agentic Retrieval App Agent | You need Azure AI Search agentic retrieval with knowledge bases, knowledge sources, query planning, references, or activity logs. |
| Document Processing App Agent | You need structured document extraction. |
| Document Extraction App Agent | You need preconfigured invoice, receipt, form, ID, custom field, classifier, or composed-model extraction. |
| Document Knowledge Pipeline Agent | You need Document Intelligence output in Azure AI Search, knowledge mining, RAG, metadata enrichment, citations, or batch pipelines. |

Use these shared platform specialists as needed:

| Specialist | Use when |
| --- | --- |
| Auth Config Agent | You need `.env`, local auth, Entra ID, or endpoint validation guidance. |
| Foundry Integration Agent | You need Foundry project, model deployment, quota, or endpoint guidance. |
| Responsible AI Safety Agent | You need moderation, safety policy, or evaluation checks. |

## Recommended First Prompt

Start here:

```text
/learn-ai-capability Start with Azure AI Services foundations and give me the first hands-on exercise.
```
