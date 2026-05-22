import {
  ConnectionState,
  Room,
  RoomEvent,
  Track,
  type Participant,
  type TranscriptionSegment,
} from "livekit-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { getVoiceToken } from "../api/client";
import { useConversationStore } from "../stores/conversationStore";
export type VoiceSessionState = "idle" | "connecting" | "listening" | "speaking" | "error";

export function useVoiceSession(projectId: string, enabled: boolean) {
  const appendMessage = useConversationStore((s) => s.appendMessage);
  const seenSegments = useRef(new Set<string>());

  const roomRef = useRef<Room | null>(null);
  const [room, setRoom] = useState<Room | null>(null);
  const [connected, setConnected] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceSessionState>("idle");
  const [error, setError] = useState<string | null>(null);

  const handleTranscription = useCallback(
    (segments: TranscriptionSegment[], participant?: Participant) => {
      if (!participant) return;
      const role = participant.isLocal ? "user" : "assistant";
      for (const seg of segments) {
        if (!seg.final || !seg.text.trim()) continue;
        if (seenSegments.current.has(seg.id)) continue;
        seenSegments.current.add(seg.id);
        appendMessage({ role, text: seg.text.trim() });
      }
    },
    [appendMessage],
  );

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
    setError(null);
  }, []);

  useEffect(() => {
    seenSegments.current.clear();
    return () => {
      void disconnect();
    };
  }, [disconnect, projectId]);

  const connect = useCallback(async () => {
    if (!enabled || connected) return;
    setError(null);
    setVoiceState("connecting");

    try {
      const { token, url } = await getVoiceToken(projectId);
      const lkRoom = new Room({ adaptiveStream: true, dynacast: true });
      roomRef.current = lkRoom;
      setRoom(lkRoom);

      lkRoom.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
        if (state === ConnectionState.Connected) {
          setConnected(true);
          setVoiceState("listening");
        }
        if (state === ConnectionState.Disconnected) {
          setConnected(false);
          setVoiceState("idle");
        }
      });

      lkRoom.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          el.id = "bim-agent-audio";
          document.body.appendChild(el);
          setVoiceState("speaking");
        }
      });

      lkRoom.on(RoomEvent.TrackUnsubscribed, (track) => {
        track.detach().forEach((el) => el.remove());
        if (lkRoom.state === ConnectionState.Connected) setVoiceState("listening");
      });

      lkRoom.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const agentSpeaking = speakers.some((p) => !p.isLocal);
        if (agentSpeaking) setVoiceState("speaking");
        else if (lkRoom.state === ConnectionState.Connected) setVoiceState("listening");
      });

      lkRoom.on(RoomEvent.TranscriptionReceived, handleTranscription);

      await lkRoom.connect(url, token);
      await lkRoom.localParticipant.setMicrophoneEnabled(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setVoiceState("error");
      await disconnect();
    }
  }, [connected, disconnect, enabled, handleTranscription, projectId]);

  const stringActive =
    connected ||
    voiceState === "connecting" ||
    voiceState === "listening" ||
    voiceState === "speaking";

  return {
    room,
    connected,
    voiceState,
    error,
    stringActive,
    connect,
    disconnect,
  };
}
