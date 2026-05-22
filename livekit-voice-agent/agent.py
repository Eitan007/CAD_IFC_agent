"""
LiveKit voice worker — routes spoken questions to the BIM FastAPI agent (same as text chat).
"""
from __future__ import annotations

import json
import logging
import os

import httpx
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    TurnHandlingOptions,
    cli,
    function_tool,
    inference,
    llm,
    room_io,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger(__name__)

load_dotenv()

BIM_API_BASE = os.getenv("BIM_API_BASE", "http://127.0.0.1:8000").rstrip("/")


async def _call_bim_chat(project_id: str, message: str, selected_element: str | None = None) -> str:
    payload = {"message": message, "selected_element": selected_element}
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(
            f"{BIM_API_BASE}/api/projects/{project_id}/chat",
            json=payload,
        )
        res.raise_for_status()
        data = res.json()
    return str(data.get("answer") or data.get("explanation") or "No answer returned.")


class BIMAssistant(Agent):
    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        super().__init__(
            instructions=(
                "You are Jarvis, a voice BIM assistant for building models. "
                "For any question about quantities, elements, cost, schedule, compliance, or the model, "
                "you MUST call the query_building_model tool — never invent building data. "
                "Speak answers clearly and keep responses under 4 sentences unless the user asks for detail."
            )
        )

    @function_tool
    async def query_building_model(self, context: RunContext, question: str) -> str:
        """
        Query the project's BIM knowledge graph (same backend as text chat).
        Use for all building-model questions.
        """
        selected: str | None = None
        try:
            ud = context.userdata
            if isinstance(ud, dict):
                raw = ud.get("selected_element")
                selected = str(raw) if raw else None
        except ValueError:
            pass  # session started without userdata — optional UI selection
        try:
            return await _call_bim_chat(self._project_id, question, selected)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:200] if exc.response else str(exc)
            logger.warning("BIM chat HTTP error: %s", detail)
            return f"I could not reach the building database: {detail}"
        except Exception as exc:
            logger.exception("BIM chat failed")
            return f"Sorry, the building query failed: {exc}"


server = AgentServer(num_idle_processes=0)


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}

    meta: dict = {}
    try:
        meta = json.loads(ctx.room.metadata or "{}")
    except json.JSONDecodeError:
        logger.warning("Invalid room metadata JSON")

    project_id = meta.get("project_id") or ""
    if not project_id and ctx.room.name.startswith("bim-"):
        project_id = ctx.room.name[4:]

    if not project_id:
        logger.error("No project_id in room metadata — cannot serve BIM voice")
        return

    ctx.proc.userdata["project_id"] = project_id
    turn_detector = MultilingualModel()

    session = AgentSession(
        userdata={"selected_element": None},
        stt=inference.STT(
            "assemblyai/universal-streaming",
            language="en",
            fallback=["deepgram/nova-3"],
        ),
        llm=llm.FallbackAdapter(
            [
                inference.LLM("openai/gpt-4.1-mini"),
                inference.LLM("google/gemini-2.5-flash"),
            ]
        ),
        tts=inference.TTS(
            "cartesia/sonic-3",
            fallback=["inworld/inworld-tts-1"],
        ),
        vad=ctx.proc.userdata["vad"],
        turn_handling=TurnHandlingOptions(
            turn_detection=turn_detector,
            interruption={
                "resume_false_interruption": True,
                "false_interruption_timeout": 1.0,
            },
            preemptive_generation={"enabled": True},
        ),
        aec_warmup_duration=3.0,
    )

    await session.start(
        agent=BIMAssistant(project_id=project_id),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(server)
