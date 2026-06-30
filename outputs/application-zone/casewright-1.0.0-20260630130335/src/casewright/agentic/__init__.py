"""Agentic RAG engine ported from case-assistant-agent.

Reproduces the multi-agent agentic retrieval behaviour (HyDE query rewriting →
reflection retry loop → cited answer generation) on top of Casewright's existing
managed-identity Azure clients. No Microsoft Agent Framework dependency — the
orchestration is a plain async loop and the LLM calls go through the standard
``openai`` SDK already used by Casewright.
"""
