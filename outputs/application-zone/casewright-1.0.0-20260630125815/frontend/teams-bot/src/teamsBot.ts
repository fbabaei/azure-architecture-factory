import {
  AgentApplication,
  MemoryStorage,
  MessageFactory,
  TurnContext,
  TurnState,
} from "@microsoft/agents-hosting";
import { SSOCommandMap } from "./commands/SSOCommandMap";
import config from "./config";
import {
  AgentClient,
  conversationIdToSessionId,
  QueryResponse,
} from "./agentClient";
import { buildAnswerCard } from "./answerCard";
import {
  ALL_SITES_VALUE,
  SITE_PICKER_ACTION,
  buildSitePickerCard,
} from "./sitePicker";

/** Conversation-state path holding the SharePoint site the user scoped to. */
const SITE_ID_STATE_PATH = "conversation.siteId";

export class TeamsBot extends AgentApplication<TurnState> {
  private readonly agentClient = new AgentClient(config.agentUrl);

  constructor() {
    super({
      storage: new MemoryStorage(),
      authorization: {
        graph: { name: config.botSsoConnectionName },
      },
    });

    this.onConversationUpdate("membersAdded", async (context: TurnContext, _state: TurnState) => {
      const membersAdded = context.activity.membersAdded ?? [];
      for (let cnt = 0; cnt < membersAdded.length; cnt++) {
        if (membersAdded[cnt].id) {
          await context.sendActivity(
            "Welcome to Casewright! Ask me a question, type 'sites' to scope to a SharePoint site, or 'show' to see your profile.",
          );
          break;
        }
      }
    });

    this.authorization.onSignInSuccess(async (_context: TurnContext, _state: TurnState) => {
      console.log("User signed in successfully.");
    });

    this.authorization.onSignInFailure(async (context: TurnContext, _state: TurnState, authId?: string, err?: string) => {
      console.error(`Sign in failure in ${authId}: ${err}`);
      await context.sendActivity(MessageFactory.text("Sign in failed. Please try again."));
    });

    this.onError(async (_context: TurnContext, err: unknown) => {
      console.error("Unhandled error in bot:", err);
    });

    this.onMessage("logout", async (context: TurnContext, state: TurnState) => {
      await this.authorization.signOut(context, state, "graph");
      await context.sendActivity(MessageFactory.text("You have been signed out."));
    });

    // Generic message handler. SSO is only triggered when the user explicitly
    // invokes an SSO command (e.g. "show") — free-form messages are routed to
    // the backend without requiring a Teams tenant, which lets the bot run in
    // the Agents Playground with empty clientId/tenantId.
    this.onActivity("message", async (context: TurnContext, state: TurnState) => {
      console.log("Running with Message Activity.");

      // Adaptive Card submit from the site picker arrives as a message activity
      // with an empty text body and a populated `value`. Handle it first.
      const cardValue = context.activity.value as
        | { action?: string; siteId?: string }
        | undefined;
      if (cardValue?.action === SITE_PICKER_ACTION) {
        await this.handleSiteSelection(context, state, cardValue.siteId);
        return;
      }

      let txt = context.activity.text ?? "";
      const removedMentionText = context.activity.removeRecipientMention();
      if (removedMentionText) {
        txt = removedMentionText.toLowerCase().replace(/\n|\r/g, "").trim();
      }

      // Site-scoping command: show the picker card.
      if (
        txt === "sites" ||
        txt === "site" ||
        txt === "select site" ||
        txt === "change site"
      ) {
        await this.handleShowSitePicker(context);
        return;
      }

      const SSOCommand = SSOCommandMap.get(txt);
      if (SSOCommand) {
        try {
          const tokenResponse = await this.authorization.getToken(context, "graph");
          if (!tokenResponse?.token) {
            await context.sendActivity(
              MessageFactory.text("Unable to get token. Please sign in first."),
            );
            return;
          }
          await SSOCommand.operationWithToken(context, tokenResponse.token);
        } catch (err) {
          console.error("SSO command failed:", err);
          await context.sendActivity(
            MessageFactory.text(
              "SSO isn't configured for this environment. Ask me an IT question instead.",
            ),
          );
        }
        return;
      }

      await this.handleAgenticQuery(context, state, txt);
    });
  }

  /**
   * Show the SharePoint site picker so the user can scope retrieval to one site.
   */
  private async handleShowSitePicker(context: TurnContext): Promise<void> {
    let bearerToken: string | undefined;
    try {
      const tokenResponse = await this.authorization.getToken(context, "graph");
      bearerToken = tokenResponse?.token;
    } catch {
      // Non-fatal: backend may list sites with its own app identity in dev.
    }

    try {
      const sites = await this.agentClient.getSites(bearerToken);
      if (sites.length === 0) {
        await context.sendActivity(
          MessageFactory.text("No SharePoint sites are available to scope to."),
        );
        return;
      }
      await context.sendActivity(
        MessageFactory.attachment(buildSitePickerCard(sites)),
      );
    } catch (err) {
      console.error("Failed to load sites:", err);
      await context.sendActivity(
        MessageFactory.text(
          "Sorry, I couldn't load the list of SharePoint sites right now.",
        ),
      );
    }
  }

  /**
   * Persist the site selected in the picker card to conversation state so that
   * subsequent questions are scoped to it. Selecting "All sites" clears it.
   */
  private async handleSiteSelection(
    context: TurnContext,
    state: TurnState,
    siteId?: string,
  ): Promise<void> {
    if (!siteId || siteId === ALL_SITES_VALUE) {
      state.deleteValue(SITE_ID_STATE_PATH);
      await context.sendActivity(
        MessageFactory.text("Site scoping cleared — I'll search across all sites."),
      );
      return;
    }

    state.setValue(SITE_ID_STATE_PATH, siteId);
    await context.sendActivity(
      MessageFactory.text(
        "Got it — I'll scope answers to the selected site. Ask your question, or type 'sites' to change.",
      ),
    );
  }

  /**
   * Forward the user's message to the Casewright backend and render
   * the response in Teams.
   */
  private async handleAgenticQuery(
    context: TurnContext,
    state: TurnState,
    text: string,
  ): Promise<void> {
    const userText = (text || context.activity.text || "").trim();

    if (!userText) {
      return;
    }

    const userId =
      context.activity.from?.aadObjectId ||
      context.activity.from?.id ||
      "anonymous";
    const sessionId = conversationIdToSessionId(
      context.activity.conversation?.id ?? `user-${userId}`,
    );

    // Restrict retrieval to the site the user scoped to (if any).
    const siteId = state.getValue<string | undefined>(SITE_ID_STATE_PATH);

    // Optional: pass through Teams SSO token if backend auth is enabled.
    let bearerToken: string | undefined;
    try {
      const tokenResponse = await this.authorization.getToken(context, "graph");
      bearerToken = tokenResponse?.token;
    } catch {
      // Non-fatal: backend currently allows unauthenticated requests in dev.
    }

    // Show a "…" typing indicator while the backend runs. Teams auto-expires
    // the indicator after ~10s, so refresh it every 4s until the call returns.
    const sendTyping = () =>
      context
        .sendActivity({ type: "typing" } as unknown as Parameters<typeof context.sendActivity>[0])
        .catch(() => undefined);
    await sendTyping();
    const typingTimer = setInterval(sendTyping, 4000);

    try {
      const response: QueryResponse = await this.agentClient.query({
        query: userText,
        userId,
        sessionId,
        bearerToken,
        siteId,
      });

      await context.sendActivity(
        MessageFactory.attachment(buildAnswerCard(response, config.agentUrl)),
      );
    } catch (err) {
      console.error("Agent query failed:", err);
      await context.sendActivity(
        MessageFactory.text(
          "Sorry, I couldn't reach the Casewright agent right now. Please try again shortly.",
        ),
      );
    } finally {
      clearInterval(typingTimer);
    }
  }
}
