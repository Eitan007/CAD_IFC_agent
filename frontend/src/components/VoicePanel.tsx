import {
  ConnectionState,
  Room,
  RoomEvent,
  Track,
} from "livekit-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { getVoiceToken } from "../api/client";
import { useUiStore } from "../stores/uiStore";
import { VoiceStringVisualizer } from "./VoiceStringVisualizer";

type VoiceState = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error";

type Props = {
  projectId: string;
  voiceEnabled: boolean;
};

export function VoicePanel({ projectId, voiceEnabled }: Props) {
  const selectedElementId = useUiStore((s) => s.selectedElementId);
  const roomRef = useRef<Room | null>(null);
  const [room, setRoom] = useState<Room | null>(null);

  const [connected, setConnected] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [statusLine, setStatusLine] = useState("Start a voice session with Jarvis.");
  const [error, setError] = useState<string | null>(null);

  const disconnect = useCallback(async () => {
    const activeRoom = roomRef.current;
    roomRef.current = null;
    setRoom(null);
    if (activeRoom) {
      await activeRoom.disconnect();
    }
    document.querySelectorAll("#bim-agent-audio").forEach((el) => el.remove());
    setConnected(false);
    setVoiceState("idle");
    setStatusLine("Disconnected.");
  }, []);

  useEffect(() => {
    return () => {
      void disconnect();
    };
  }, [disconnect, projectId]);

  const connect = async () => {
    if (!voiceEnabled || connected) return;
    setError(null);
    setVoiceState("connecting");
    setStatusLine("Connecting to voice room…");

    try {
      const { token, url } = await getVoiceToken(projectId);
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });
      roomRef.current = room;
      setRoom(room);

      room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
        if (state === ConnectionState.Connected) {
          setConnected(true);
          setVoiceState("listening");
          setStatusLine("Listening — ask about your building model.");
        }
        if (state === ConnectionState.Disconnected) {
          setConnected(false);
          setVoiceState("idle");
        }
      });

      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          el.id = "bim-agent-audio";
          document.body.appendChild(el);
          setVoiceState("speaking");
          setStatusLine("Jarvis is speaking…");
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        track.detach().forEach((el) => el.remove());
        setVoiceState("listening");
        setStatusLine("Listening — ask about your building model.");
      });

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const agentSpeaking = speakers.some((p) => !p.isLocal);
        if (agentSpeaking) {
          setVoiceState("speaking");
          setStatusLine("Jarvis is speaking…");
        } else if (roomRef.current?.state === ConnectionState.Connected) {
          setVoiceState("listening");
          setStatusLine("Listening…");
        }
      });

      await room.connect(url, token);
      await room.localParticipant.setMicrophoneEnabled(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setVoiceState("error");
      setStatusLine("Could not connect.");
      await disconnect();
    }
  };

  const stringActive =
    connected ||
    voiceState === "connecting" ||
    voiceState === "listening" ||
    voiceState === "speaking" ||
    voiceState === "thinking";

  return (
    <div className="voice-pane">
      <div style={{ padding: "0.65rem 0.75rem", borderBottom: "1px solid color-mix(in srgb, var(--cyan) 20%, transparent)" }}>
        <div style={{ fontWeight: 700 }}>Voice assistant</div>
        <div className="muted" style={{ marginTop: "0.25rem", fontSize: "0.85rem" }}>
          Same BIM agent as text chat — powered by LiveKit + backend tools.
        </div>
        {selectedElementId && (
          <div className="muted" style={{ marginTop: "0.35rem", fontSize: "0.82rem" }}>
            Selected element: <code>{selectedElementId}</code>
          </div>
        )}
      </div>

      <div className="voice-stage">
        <VoiceStringVisualizer room={room} active={stringActive} />

        <p className="voice-status">{statusLine}</p>
        {error && (
          <p className="voice-error" role="alert">
            {error}
          </p>
        )}
      </div>

      <div className="voice-actions">
        {!connected ? (
          <button
            type="button"
            className="btn-voice"
            disabled={!voiceEnabled || voiceState === "connecting"}
            onClick={() => void connect()}
          >
            {voiceEnabled ? "Start voice" : "Voice unlocks after pipeline"}
          </button>
        ) : (
          <button type="button" className="btn-voice btn-voice-end" onClick={() => void disconnect()}>
            End session
          </button>
        )}
      </div>
    </div>
  );
}
