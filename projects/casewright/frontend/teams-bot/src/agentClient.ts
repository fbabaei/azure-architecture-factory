/**
 * HTTP client for the Casewright FastAPI backend (`/api/chat`).
 *
 * Maps Teams activity fields to the backend's `ChatRequest` schema and
 * returns the parsed `ChatResponse`. The conversation_id is derived from the
 * Teams conversation id (namespaced UUID v5 so it is stable per conversation
 * and round-trips cleanly through the backend).
 */

import { createHash } from "crypto";

export interface Citation {
  document_title?: string;
  source_path?: string;
  score?: number;
  [key: string]: unknown;
}

export interface QueryResponse {
  conversation_id?: string;
  answer: string;
  citations: Citation[];
  runtime?: "foundry" | "local";
  [key: string]: unknown;
}

export interface QueryInput {
  query: string;
  userId: string;
  sessionId: string;
  bearerToken?: string;
}

/**
 * Produce a deterministic UUID v5-style identifier from an arbitrary string.
 *
 * The Teams conversation id is an opaque string; hashing it yields a stable
 * 36-char UUID for the lifetime of the conversation without requiring a
 * separate mapping store. Casewright accepts any conversation_id string, so a
 * stable derived id keeps history coherent per Teams chat.
 */
export function conversationIdToSessionId(conversationId: string): string {
  const hash = createHash("sha1").update(conversationId).digest("hex");
  return [
    hash.substring(0, 8),
    hash.substring(8, 12),
    // Force version 5 nibble
    "5" + hash.substring(13, 16),
    // Force variant 10xx nibble
    ((parseInt(hash.substring(16, 17), 16) & 0x3) | 0x8).toString(16) +
      hash.substring(17, 20),
    hash.substring(20, 32),
  ].join("-");
}

export class AgentClient {
  constructor(private readonly baseUrl: string) {
    if (!baseUrl) {
      throw new Error("AGENT_URL must be configured.");
    }
  }

  async query(input: QueryInput): Promise<QueryResponse> {
    const url = `${this.baseUrl.replace(/\/$/, "")}/api/chat`;

    const body: Record<string, unknown> = {
      message: input.query,
      conversation_id: input.sessionId,
      user_id: input.userId,
      tenant_id: "default",
    };

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (input.bearerToken) {
      headers["Authorization"] = `Bearer ${input.bearerToken}`;
    }

    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(
        `Agent query failed: ${res.status} ${res.statusText}${text ? ` — ${text}` : ""}`,
      );
    }

    return (await res.json()) as QueryResponse;
  }
}
