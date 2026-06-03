import {
  ConnectionState,
  Room,
  RoomEvent,
  Track,
  type Participant,
  type TranscriptionSegment,
} from "livekit-client";
import { getVoiceToken } from "../api/client";

export type VoiceConnectionState = "idle" | "connecting" | "listening" | "speaking" | "error";

export type VoiceRoomSnapshot = {
  room: Room | null;
  connectionState: VoiceConnectionState;
  connected: boolean;
  error: string | null;
};

type SessionCallbacks = {
  onTranscription?: (role: "user" | "assistant", text: string) => void;
  onAgentDisconnected?: () => void;
  onResponseTimeout?: () => void;
};

const RESPONSE_TIMEOUT_MS = 30_000;

type ManagedSession = {
  room: Room;
  projectId: string;
  callbacks: Set<SessionCallbacks>;
  seenSegments: Set<string>;
  responseTimeout: ReturnType<typeof setTimeout> | null;
  agentParticipantSid: string | null;
  connectionState: VoiceConnectionState;
  error: string | null;
  connectPromise: Promise<Room> | null;
  lastSnapshot?: VoiceRoomSnapshot;
  shouldBeConnected: boolean;
};

const sessions = new Map<string, ManagedSession>();
const listeners = new Set<() => void>();

const EMPTY_SNAPSHOT: VoiceRoomSnapshot = {
  room: null,
  connectionState: "idle",
  connected: false,
  error: null,
};

function emit() {
  for (const fn of listeners) {
    fn();
  }
}

function snapshot(projectId: string): VoiceRoomSnapshot {
  const session = sessions.get(projectId);
  if (!session) return EMPTY_SNAPSHOT;

  const connected = session.room.state === ConnectionState.Connected;

  if (
    session.lastSnapshot &&
    session.lastSnapshot.room === session.room &&
    session.lastSnapshot.connectionState === session.connectionState &&
    session.lastSnapshot.connected === connected &&
    session.lastSnapshot.error === session.error
  ) {
    return session.lastSnapshot;
  }

  session.lastSnapshot = {
    room: session.room,
    connectionState: session.connectionState,
    connected,
    error: session.error,
  };
  return session.lastSnapshot;
}

export function subscribeVoiceRoom(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getVoiceRoomSnapshot(projectId: string): VoiceRoomSnapshot {
  return snapshot(projectId);
}

function clearResponseTimeout(session: ManagedSession) {
  if (session.responseTimeout) {
    clearTimeout(session.responseTimeout);
    session.responseTimeout = null;
  }
}

function startResponseTimeout(session: ManagedSession) {
  clearResponseTimeout(session);
  session.responseTimeout = setTimeout(() => {
    if (session.room.state === ConnectionState.Connected) {
      session.connectionState = "error";
      session.error = "Agent not responding. Please try again.";
      for (const cb of session.callbacks) {
        cb.onResponseTimeout?.();
      }
      emit();
    }
  }, RESPONSE_TIMEOUT_MS);
}

function handleTranscription(
  session: ManagedSession,
  segments: TranscriptionSegment[],
  participant?: Participant,
) {
  clearResponseTimeout(session);
  if (!participant) return;
  const role = participant.isLocal ? "user" : "assistant";
  for (const seg of segments) {
    if (!seg.final || !seg.text.trim()) continue;
    if (session.seenSegments.has(seg.id)) continue;
    session.seenSegments.add(seg.id);
    const text = seg.text.trim();
    for (const cb of session.callbacks) {
      cb.onTranscription?.(role, text);
    }
  }
}

function wireRoomEvents(session: ManagedSession) {
  const { room } = session;

  room.on(RoomEvent.LocalTrackPublished, () => {
    startResponseTimeout(session);
    emit();
  });

  room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
    if (state === ConnectionState.Connected) {
      session.connectionState = "listening";
      session.error = null;
    }
    if (state === ConnectionState.Disconnected) {
      clearResponseTimeout(session);
      session.connectionState = "idle";
      session.agentParticipantSid = null;
      
      // Auto-reconnect if should be connected
      if (session.shouldBeConnected) {
        console.log("Room disconnected, attempting auto-reconnect...");
        setTimeout(() => {
          void ensureVoiceRoomConnected(session.projectId);
        }, 1000);
      }
    }
    emit();
  });

  room.on(RoomEvent.ParticipantConnected, (participant) => {
    if (!participant.isLocal) {
      session.agentParticipantSid = participant.sid;
      session.error = null;
      if (session.connectionState === "error") {
        session.connectionState = "listening";
      }
      emit();
    }
  });

  room.on(RoomEvent.ParticipantDisconnected, (participant) => {
    if (!participant.isLocal && participant.sid === session.agentParticipantSid) {
      session.agentParticipantSid = null;
      clearResponseTimeout(session);
      
      if (session.shouldBeConnected) {
         session.connectionState = "connecting";
         session.error = "Agent disconnected. Reconnecting...";
         const pid = session.projectId;
         void endVoiceSession(pid).then(() => {
           return ensureVoiceRoomConnected(pid);
         });
      } else {
        session.connectionState = "error";
        session.error = "Agent session ended. Open voice again to reconnect.";
      }
      
      for (const cb of session.callbacks) {
        cb.onAgentDisconnected?.();
      }
      emit();
    }
  });

  room.on(RoomEvent.TrackSubscribed, (track) => {
    if (track.kind === Track.Kind.Audio) {
      clearResponseTimeout(session);
      const el = track.attach();
      el.id = "bim-agent-audio";
      document.body.appendChild(el);
      session.connectionState = "speaking";
      emit();
    }
  });

  room.on(RoomEvent.TrackUnsubscribed, (track) => {
    track.detach().forEach((el) => el.remove());
    if (room.state === ConnectionState.Connected) {
      session.connectionState = "listening";
      emit();
    }
  });

  room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
    const agentSpeaking = speakers.some((p) => !p.isLocal);
    if (agentSpeaking) {
      session.connectionState = "speaking";
    } else if (room.state === ConnectionState.Connected) {
      session.connectionState = "listening";
    }
    emit();
  });

  room.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
    handleTranscription(session, segments, participant);
  });
}

function removeAgentAudioElements() {
  document.querySelectorAll("#bim-agent-audio").forEach((el) => el.remove());
}

/** Connect or reuse an existing LiveKit room for this project. */
export async function ensureVoiceRoomConnected(projectId: string): Promise<Room> {
  let session = sessions.get(projectId);

  if (session?.connectionState === "error") {
    // If it was in error but NOT shouldBeConnected, we clean up.
    // If it was shouldBeConnected, we'll try again anyway.
    if (!session.shouldBeConnected) {
      await endVoiceSession(projectId);
      session = undefined;
    }
  }

  session = getOrCreateSession(projectId);
  session.shouldBeConnected = true; // Mark as wanting to be connected

  if (session.room.state === ConnectionState.Connected) {
    session.error = null;
    if (session.connectionState === "error" || session.connectionState === "idle") {
      session.connectionState = "listening";
    }
    emit();
    return session.room;
  }

  if (session.connectPromise) {
    return session.connectPromise;
  }

  if (session.room.state === ConnectionState.Disconnected && session.connectionState !== "idle") {
    try {
      await session.room.disconnect();
    } catch {
      /* already disconnected */
    }
    removeAgentAudioElements();
    session.seenSegments.clear();
    session.connectionState = "idle";
    session.agentParticipantSid = null;
  }

  session.connectionState = "connecting";
  session.error = null;
  emit();

  const connectPromise = (async () => {
    try {
      const { token, url } = await getVoiceToken(projectId);
      await session.room.connect(url, token);
      session.connectionState = "listening";
      session.error = null;
      emit();
      return session.room;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      session.connectionState = "error";
      session.error = msg;
      emit();
      // Don't call endVoiceSession here if we want to retry, 
      // but for now let's keep it simple.
      throw err;
    } finally {
      session.connectPromise = null;
    }
  })();

  session.connectPromise = connectPromise;
  return connectPromise;
}

export async function setVoiceMicrophoneEnabled(projectId: string, enabled: boolean): Promise<void> {
  const session = sessions.get(projectId);
  if (!session || session.room.state !== ConnectionState.Connected) return;
  await session.room.localParticipant.setMicrophoneEnabled(enabled);
}

function getOrCreateSession(projectId: string): ManagedSession {
  let session = sessions.get(projectId);
  if (!session) {
    session = {
      room: new Room({ adaptiveStream: true, dynacast: true }),
      projectId,
      callbacks: new Set(),
      seenSegments: new Set(),
      responseTimeout: null,
      agentParticipantSid: null,
      connectionState: "idle",
      error: null,
      connectPromise: null,
      shouldBeConnected: false,
    };
    sessions.set(projectId, session);
    wireRoomEvents(session);
  }
  return session;
}

export function registerVoiceCallbacks(projectId: string, callbacks: SessionCallbacks): () => void {
  const session = getOrCreateSession(projectId);
  session.callbacks.add(callbacks);
  return () => {
    session.callbacks.delete(callbacks);
  };
}

/** Mute mic but keep the LiveKit room (and agent) alive. */
export async function pauseVoiceSession(projectId: string): Promise<void> {
  await setVoiceMicrophoneEnabled(projectId, false);
}

/** Fully disconnect and remove the room for this project. */
export async function endVoiceSession(projectId: string): Promise<void> {
  const session = sessions.get(projectId);
  if (!session) return;

  session.shouldBeConnected = false; // Stop wanting to be connected
  clearResponseTimeout(session);
  sessions.delete(projectId);

  try {
    await session.room.localParticipant.setMicrophoneEnabled(false);
    await session.room.disconnect();
  } catch {
    /* ignore */
  }
  removeAgentAudioElements();
  emit();
}
