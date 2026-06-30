/**
 * Adaptive Card for selecting a SharePoint site to scope retrieval to.
 *
 * Enforces the "strict site isolation" principle: the user picks one SharePoint
 * site and every subsequent question is grounded only in that site's documents
 * (the backend applies a `site_id` filter). Picking "All sites" clears scoping.
 */

import type { Attachment } from "@microsoft/agents-activity";
import { CardFactory } from "@microsoft/agents-hosting";
import type { SiteInfo } from "./agentClient";

/** Action name carried in the card's Action.Submit `data`, used to route the submit. */
export const SITE_PICKER_ACTION = "selectSite";

/** Sentinel choice value meaning "do not scope to any site". */
export const ALL_SITES_VALUE = "__all__";

export function buildSitePickerCard(
  sites: SiteInfo[],
  currentSiteId?: string,
): Attachment {
  const choices = [
    { title: "All sites (no scoping)", value: ALL_SITES_VALUE },
    ...sites.map((s) => ({ title: s.displayName, value: s.id })),
  ];

  return CardFactory.adaptiveCard({
    $schema: "http://adaptivecards.io/schemas/adaptive-card.json",
    type: "AdaptiveCard",
    version: "1.5",
    body: [
      {
        type: "TextBlock",
        text: "Select a SharePoint site",
        weight: "Bolder",
        size: "Medium",
        color: "Accent",
      },
      {
        type: "TextBlock",
        text: "Answers will be grounded only in the selected site's documents.",
        wrap: true,
        isSubtle: true,
        spacing: "Small",
      },
      {
        type: "Input.ChoiceSet",
        id: "siteId",
        style: "compact",
        value: currentSiteId ?? ALL_SITES_VALUE,
        choices,
      },
    ],
    actions: [
      {
        type: "Action.Submit",
        title: "Use this site",
        data: { action: SITE_PICKER_ACTION },
      },
    ],
  });
}
