/**
 * Adaptive Card builders for agent responses.
 */

import type { Attachment } from "@microsoft/agents-activity";
import { CardFactory } from "@microsoft/agents-hosting";
import type { Citation, QueryResponse } from "./agentClient";

const ADAPTIVE_CARD_VERSION = "1.5";

export function buildAnswerCard(
  response: QueryResponse,
  backendUrl?: string,
): Attachment {
  const body: Array<Record<string, unknown>> = [
    {
      type: "TextBlock",
      text: "Casewright",
      weight: "Bolder",
      size: "Medium",
      color: "Accent",
    },
    {
      type: "TextBlock",
      text: response.answer || "(no answer returned)",
      wrap: true,
    },
  ];

  const citations = response.citations ?? [];
  if (citations.length > 0) {
    body.push({
      type: "TextBlock",
      text: "Sources",
      weight: "Bolder",
      spacing: "Medium",
      separator: true,
    });
    citations.forEach((c, i) => {
      body.push({
        type: "TextBlock",
        text: formatCitation(c, i + 1, backendUrl),
        wrap: true,
        spacing: "Small",
      });
    });
  }

  return CardFactory.adaptiveCard({
    $schema: "http://adaptivecards.io/schemas/adaptive-card.json",
    type: "AdaptiveCard",
    version: ADAPTIVE_CARD_VERSION,
    body,
  });
}

function formatCitation(c: Citation, index: number, backendUrl?: string): string {
  const title =
    c.document_title ||
    c.content_id ||
    c.document_id ||
    "Source";
  const page = c.page_number ? ` (p.${c.page_number})` : "";
  const link = citationLink(c, backendUrl);
  const titleWithPage = `${title}${page}`;
  // Use bracketed prefix so Adaptive Cards' markdown parser doesn't treat
  // "1. ..." as an ordered list (which strips/renumbers the prefix).
  const linkedTitle = link ? `[${titleWithPage}](${link})` : titleWithPage;
  return `**[${index}]** ${linkedTitle}`;
}

/**
 * The agentic Citation shape exposes no resolvable source URL, so citations
 * render as plain text. (Kept as a hook in case the backend later returns an
 * absolute content path/URL.)
 */
function citationLink(_c: Citation, _backendUrl?: string): string | undefined {
  return undefined;
}
