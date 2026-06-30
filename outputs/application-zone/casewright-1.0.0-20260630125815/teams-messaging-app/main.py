"""Composition root.

Builds the service graph and wires it into the Teams app. This file should
contain no business logic — anything beyond glue belongs in a service or
the orchestrator.

Routing behaviour:
- ``<broadcast_command>``  →  run :class:`SiteBroadcastOrchestrator`
- anything else             →  forward to the Foundry agent with per-chat
                              conversation history

Run:
    python main.py

Then in a separate terminal:
    agentsplayground -e http://localhost:3978/api/messages -c msteams
"""

from __future__ import annotations

import asyncio
import logging

from microsoft_teams.apps import App
from microsoft_teams.apps.routing.activity_context import ActivityContext

from agentService import FoundryAgentService
from boardcastOrchestrator import BroadcastResult, SiteBroadcastOrchestrator
from config import AppConfig
from conversationStore import build_conversation_store
from prompt import build_prompt
from sharepointService import SharePointService
from teamsMessenger import TeamsMessenger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("casewright-teams-messaging-app")


def _format_summary(result: BroadcastResult) -> str:
    """Render a BroadcastResult for posting back into the Teams chat."""
    if result.total_sites == 0:
        return "No SharePoint sites visible to the app."

    lines = [
        f"Broadcast complete — sites: {result.total_sites} "
        f"(with members: {result.sites_with_members}); "
        f"sent: {result.total_sent}, skipped: {result.total_skipped}.",
        "",
    ]
    for s in result.per_site:
        if s.error:
            lines.append(f"- {s.site_name}: {s.error}")
        elif s.members_total == 0:
            lines.append(f"- {s.site_name}: no members")
        else:
            lines.append(
                f"- {s.site_name}: sent={s.sent}, "
                f"unknown={s.skipped_unknown}, "
                f"failed={s.skipped_send_error} "
                f"(of {s.members_total} members)"
            )
    return "\n".join(lines)


async def _run() -> None:
    config = AppConfig.from_env()

    # Build services.
    sharepoint_service = SharePointService()
    agent_service = FoundryAgentService(
        project_endpoint=config.project_endpoint,
        agent_name=config.agent_name,
    )

    app = App(skip_auth=config.skip_auth)
    store = build_conversation_store(
        cosmos_endpoint=config.cosmos_endpoint,
        cosmos_database=config.cosmos_database,
        cosmos_container=config.cosmos_container,
        cosmos_key=config.cosmos_key,
    )
    messenger = TeamsMessenger(app, store)

    orchestrator = SiteBroadcastOrchestrator(
        sharepoint_service=sharepoint_service,
        agent_service=agent_service,
        messenger=messenger,
        prompt_builder=build_prompt,
    )

    # Teams routing — handler is thin: register the user, then route.
    @app.on_message
    async def on_message(ctx: ActivityContext) -> None:
        user_text = (ctx.activity.text or "").strip()
        if not user_text:
            return

        await messenger.register_user(
            getattr(ctx.activity.from_, "aad_object_id", None),
            ctx.activity.conversation.id,
            tenant_id=getattr(ctx.activity.conversation, "tenant_id", None),
            service_url=getattr(ctx.activity, "service_url", None),
            channel_id=getattr(ctx.activity, "channel_id", None),
            bot_id=getattr(getattr(ctx.activity, "recipient", None), "id", None),
        )

        if user_text.lower() == config.broadcast_command:
            await ctx.send(
                "Starting site broadcast — I'll DM each site's members "
                "and report back here."
            )
            try:
                result = await orchestrator.run()
            except Exception:
                logger.exception("Broadcast failed")
                await ctx.send("Broadcast failed — check server logs.")
                return
            await ctx.send(_format_summary(result))
            return

        try:
            reply = await agent_service.ask_in_chat(
                ctx.activity.conversation.id, user_text
            )
        except Exception:
            logger.exception("Agent call failed")
            reply = "Sorry — I ran into a problem reaching the agent."
        await ctx.send(reply)

    logger.info(
        "Starting Casewright Teams app on port %s (agent='%s', broadcast='%s')",
        config.port,
        config.agent_name,
        config.broadcast_command,
    )
    try:
        await app.start(port=config.port)
    finally:
        await sharepoint_service.close()
        await agent_service.close()


if __name__ == "__main__":
    asyncio.run(_run())
