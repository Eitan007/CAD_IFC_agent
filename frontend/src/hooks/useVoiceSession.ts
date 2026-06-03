import { useCallback, useEffect, useSyncExternalStore } from "react";
import {
  endVoiceSession,
  ensureVoiceRoomConnected,
  getVoiceRoomSnapshot,
  pauseVoiceSession,
  registerVoiceCallbacks,
  subscribeVoiceRoom,
  type VoiceConnectionState,
} from "../lib/voiceRoomManager";
import { useConversationStore } from "../stores/conversationStore";

export type VoiceSessionState = VoiceConnectionState;

export function useVoiceSession(projectId: string, enabled: boolean) {
  const appendMessage = useConversationStore((s) => s.appendMessage);

  const subscribe = useCallback(
    (onStoreChange: () => void) => subscribeVoiceRoom(onStoreChange),
    [],
  );
  const getSnapshot = useCallback(() => getVoiceRoomSnapshot(projectId), [projectId]);
  const snap = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useEffect(() => {
    if (!projectId || !enabled) return;
    return registerVoiceCallbacks(projectId, {
      onTranscription: (role, text) => {
        appendMessage({ role, text });
      },
    });
  }, [projectId, enabled, appendMessage]);

  // Ensure mic is off if we unmount the voice UI (safety/privacy)
  // while keeping the room connection alive in the manager.
  useEffect(() => {
    return () => {
      if (projectId) {
        void pauseVoiceSession(projectId);
      }
    };
  }, [projectId]);

  const connect = useCallback(async () => {
    if (!enabled || !projectId) return;
    try {
      const room = await ensureVoiceRoomConnected(projectId);
      await room.localParticipant.setMicrophoneEnabled(true);
    } catch {
      /* error state set in manager */
    }
  }, [enabled, projectId]);

  const pause = useCallback(async () => {
    await pauseVoiceSession(projectId);
  }, [projectId]);

  const disconnect = useCallback(async () => {
    await endVoiceSession(projectId);
  }, [projectId]);

  const stringActive =
    snap.connected ||
    snap.connectionState === "connecting" ||
    snap.connectionState === "listening" ||
    snap.connectionState === "speaking";

  return {
    room: snap.room,
    connected: snap.connected,
    voiceState: snap.connectionState,
    error: snap.error,
    stringActive,
    connect,
    pause,
    disconnect,
  };
}
