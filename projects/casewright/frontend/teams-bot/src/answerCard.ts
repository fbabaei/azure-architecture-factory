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
    fileNameFromPath(c.source_path) ||
    "Source";
  const link = citationLink(c, backendUrl);
  // Use bracketed prefix so Adaptive Cards' markdown parser doesn't treat
  // "1. ..." as an ordered list (which strips/renumbers the prefix).
  const linkedTitle = link ? `[${title}](${link})` : title;
  return `**[${index}]** ${linkedTitle}`;
}

/**
 * Render a citation link only when the source path is already an absolute
 * URL. Casewright stores `source_path` as either a blob/SharePoint URL or a
 * relative path; relative paths are shown as plain text since there is no
 * content proxy to resolve them.
 */
function citationLink(c: Citation, _backendUrl?: string): string | undefined {
  const path = c.source_path;
  if (!path) return undefined;
  if (/^https?:\/\//i.test(path)) return path;
  return undefined;
}

function fileNameFromPath(path: string | undefined): string | undefined {
  if (!path) return undefined;
  const name = decodeURIComponent(path.split(/[\\/]/).pop() || "");
  return name || undefined;
}
