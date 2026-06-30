/**
 * HTTP client for the Casewright FastAPI backend (`/api/chat/query`).
 *
 * Maps Teams activity fields to the backend's agentic `QueryRequest` schema and
 * returns the parsed `QueryResponse` (grounded answer + citations +
 * document_count). The session_id is derived from the Teams conversation id
 * (namespaced UUID v5 so it is stable per conversation and passes the backend's
 * UUID validation).
 */

import { createHash } from "crypto";

export interface Citation {
  document_id?: string;
  content_id?: string;
  content?: string;
  document_title?: string;
  page_number?: number;
  [key: string]: unknown;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  document_count: number;
  session_id?: string | null;
  thought_process?: Array<Record<string, unknown>>;
  search_history?: Array<Record<string, unknown>>;
  decisions?: string[];
  attempts?: number;
  timestamp?: string;
  [key: string]: unknown;
}

export interface QueryInput {
  query: string;
  userId: string;
  sessionId: string;
  bearerToken?: string;
  /** When set, restricts retrieval to a single SharePoint site (strict site isolation). */
  siteId?: string;
}

/** A SharePoint site the user can scope retrieval to. */
export interface SiteInfo {
  id: string;
  displayName: string;
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
    const url = `${this.baseUrl.replace(/\/$/, "")}/api/chat/query`;

    const body: Record<string, unknown> = {
      query: input.query,
      user_id: input.userId,
      session_id: input.sessionId,
    };
    if (input.siteId) {
      // Backend SearchFilters.site_id -> OData `site_id eq '...'` pre-filter.
      body.filters = { site_id: input.siteId };
    }

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

  /**
   * List the SharePoint sites available to scope retrieval to
   * (`GET /api/sharepoint/sites`).
   */
  async getSites(bearerToken?: string): Promise<SiteInfo[]> {
    const url = `${this.baseUrl.replace(/\/$/, "")}/api/sharepoint/sites`;

    const headers: Record<string, string> = {};
    if (bearerToken) {
      headers["Authorization"] = `Bearer ${bearerToken}`;
    }

    const res = await fetch(url, { method: "GET", headers });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(
        `List sites failed: ${res.status} ${res.statusText}${text ? ` — ${text}` : ""}`,
      );
    }

    const raw = (await res.json()) as Array<Record<string, unknown>>;
    return raw
      .map((s) => ({
        id: String(s.id ?? ""),
        displayName: String(s.displayName ?? s.name ?? s.id ?? "Unnamed site"),
      }))
      .filter((s) => s.id);
  }
}
