"""
LiveKit voice worker — routes spoken questions directly to the BIM FastAPI agent (Claude) and streams speech back via Cartesia TTS.
"""
from __future__ import annotations

import json
import logging
import os
import asyncio
import random

import httpx
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger(__name__)

load_dotenv()

BIM_API_BASE = os.getenv("BIM_API_BASE", "http://127.0.0.1:8000").rstrip("/")


async def _call_bim_chat(project_id: str, message: str, selected_element: str | None = None) -> str:
    payload = {"message": message, "selected_element": selected_element, "is_voice": True}
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(
            f"{BIM_API_BASE}/api/projects/{project_id}/chat",
            json=payload,
        )
        res.raise_for_status()
        data = res.json()
    return str(data.get("answer") or data.get("explanation") or "No answer returned.")


class BIMVoiceWorker(Agent):
    """Minimal agent container for the session."""
    def __init__(self) -> None:
        super().__init__(instructions="")


server = AgentServer(num_idle_processes=2)


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
    logger.info("Voice worker session starting for project_id=%s", project_id)
    
    turn_detector = MultilingualModel()

    session = AgentSession(
        userdata={"selected_element": None},
        stt=inference.STT(
            "assemblyai/universal-streaming",
            language="en",
            fallback=["deepgram/nova-3"],
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
            preemptive_generation={"enabled": False},
        ),
        aec_warmup_duration=3.0,
    )

    current_query_task: asyncio.Task | None = None

    @session.on("user_input_transcribed")
    def on_transcribed(ev) -> None:
        nonlocal current_query_task
        if not ev.is_final:
            return

        transcript = ev.transcript.strip()
        if not transcript:
            return

        logger.info("Final transcript received: %s", transcript)

        # Cancel any previous in-flight query if user spoke again
        if current_query_task and not current_query_task.done():
            current_query_task.cancel()

        async def process_voice_query(text: str) -> None:
            # 1. Start stall filler if backend takes longer than 1.2s
            stall_cancelled = False

            async def stall_routine():
                await asyncio.sleep(1.2)
                if not stall_cancelled:
                    words = text.split()
                    topic = " ".join(words[-4:]) if len(words) > 4 else "that"
                    initial_fillers = [
                        f"Let me check the building model for {topic}...",
                        f"Taking a look at {topic} now...",
                        f"Let me pull up the data for {topic}...",
                    ]
                    session.say(random.choice(initial_fillers), add_to_chat_ctx=False)

            stall_task = asyncio.create_task(stall_routine())

            # 2. Directly call the BIM backend
            selected: str | None = None
            ud = session.userdata
            if isinstance(ud, dict):
                raw = ud.get("selected_element")
                selected = str(raw) if raw else None

            try:
                answer = await _call_bim_chat(project_id, text, selected)
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text[:200] if exc.response else str(exc)
                logger.warning("BIM chat HTTP error: %s", detail)
                answer = f"I could not reach the building database: {detail}"
            except Exception as exc:
                logger.exception("BIM chat failed")
                answer = f"Sorry, the query failed: {exc}"
            finally:
                stall_cancelled = True
                stall_task.cancel()

            # 3. Speak the answer directly via Cartesia TTS
            logger.info("Speaking reply directly via TTS: %s", answer[:100])
            session.say(answer, add_to_chat_ctx=False)

        current_query_task = asyncio.create_task(process_voice_query(transcript))

    try:
        logger.info("Starting agent session for room=%s", ctx.room.name)
        await session.start(
            agent=BIMVoiceWorker(),
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    noise_cancellation=noise_cancellation.BVC(),
                ),
                # Keep agent in room when user mutes or switches to text
                close_on_disconnect=False,
            ),
        )
        logger.info("Agent session ended normally for room=%s", ctx.room.name)
    except Exception as exc:
        logger.exception("Agent session failed for room=%s: %s", ctx.room.name, exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(server)

