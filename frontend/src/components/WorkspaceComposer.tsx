import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { sendChat } from "../api/client";
import type { PipelineStatus } from "../api/types";
import { useVoiceSession } from "../hooks/useVoiceSession";
import { useConversationStore } from "../stores/conversationStore";
import { useUiStore } from "../stores/uiStore";
import { IconEqualizer, IconSendUp, IconStopSquare, IconTextCursor } from "./WorkspaceIcons";
import { VoiceStringVisualizer } from "./VoiceStringVisualizer";

export type ComposerMode = "text" | "voice";

type Props = {
  projectId: string;
  chatEnabled: boolean;
  pipelineStatus?: PipelineStatus;
  pipelineError?: string | null;
  mode: ComposerMode;
  onModeChange: (mode: ComposerMode) => void;
};

export function WorkspaceComposer({
  projectId,
  chatEnabled,
  pipelineStatus,
  pipelineError,
  mode,
  onModeChange,
}: Props) {
  const selectedElementId = useUiStore((s) => s.selectedElementId);
  const storeyFilter = useUiStore((s) => s.storeyFilter);
  const typeFilter = useUiStore((s) => s.typeFilter);
  const appendMessage = useConversationStore((s) => s.appendMessage);

  const [input, setInput] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const { room, connected, voiceState, stringActive, error, connect, disconnect } = useVoiceSession(
    projectId,
    chatEnabled,
  );

  useEffect(() => {
    if (mode === "voice" && chatEnabled && !connected && voiceState === "idle") {
      void connect();
    }
  }, [mode, chatEnabled, connected, voiceState, connect]);

  useEffect(() => {
    if (mode === "text" && connected) {
      void disconnect();
    }
  }, [mode, connected, disconnect]);

  const mutation = useMutation({
    mutationFn: async (text: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      let message = text;
      const ctx: string[] = [];
      if (selectedElementId) ctx.push(`Selected IFC express ID: ${selectedElementId}`);
      if (storeyFilter) ctx.push(`Focus storey: ${storeyFilter}`);
      if (typeFilter) ctx.push(`Focus component type: ${typeFilter}`);
      if (ctx.length) message = `${ctx.join(" | ")}\n\n${text}`;

      return sendChat(
        projectId,
        { message, selected_element: selectedElementId },
        controller.signal,
      );
    },
    onMutate: (text) => {
      appendMessage({ role: "user", text });
      appendMessage({ role: "assistant", text: "Thinking…", id: "pending-assistant" });
      setInput("");
    },
    onSuccess: (data) => {
      useConversationStore.setState((s) => ({
        messages: [
          ...s.messages.filter((m) => m.id !== "pending-assistant"),
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            text: data.answer,
            refs: data.references ?? [],
          },
        ],
      }));
    },
    onError: (err: unknown) => {
      if (err instanceof Error && err.name === "AbortError") {
        useConversationStore.setState((s) => ({
          messages: s.messages.filter((m) => m.id !== "pending-assistant"),
        }));
        return;
      }
      const msg = err instanceof Error ? err.message : String(err);
      useConversationStore.setState((s) => ({
        messages: [
          ...s.messages.filter((m) => m.id !== "pending-assistant"),
          { id: `err-${Date.now()}`, role: "assistant", text: `Request failed: ${msg}` },
        ],
      }));
    },
    onSettled: () => {
      abortRef.current = null;
    },
  });

  const handleSendOrStop = () => {
    if (mutation.isPending) {
      abortRef.current?.abort();
      mutation.reset();
      return;
    }
    if (!chatEnabled) return;
    const trimmed = input.trim();
    if (!trimmed) return;
    mutation.mutate(trimmed);
  };

  const switchToVoice = () => {
    if (!chatEnabled) return;
    onModeChange("voice");
  };

  const switchToText = () => {
    onModeChange("text");
  };

  return (
    <footer className={`ws-composer ${mode === "voice" ? "ws-composer-voice" : ""}`}>
      <div className="ws-composer-inner glass-card">
        {mode === "text" ? (
          <textarea
            className="ws-composer-input"
            placeholder={
              chatEnabled
                ? "Message the agent…"
                : pipelineStatus === "processing" || pipelineStatus === "queued"
                  ? "Parsing model — chat unlocks when Neo4j is ready…"
                  : pipelineError
                    ? `Pipeline error: ${pipelineError}`
                    : "Chat unlocks when the knowledge graph is ready…"
            }
            disabled={!chatEnabled || mutation.isPending}
            value={input}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendOrStop();
              }
            }}
          />
        ) : (
          <div className="ws-composer-voice-strip">
            <VoiceStringVisualizer room={room} active={stringActive} variant="compact" />
            {error && <p className="ws-composer-voice-err">{error}</p>}
          </div>
        )}

        <div className="ws-composer-actions">
          {mode === "text" && (
            <button
              type="button"
              className={`ws-icon-btn ws-send-btn ${mutation.isPending ? "is-stop" : ""}`}
              disabled={!chatEnabled}
              onClick={handleSendOrStop}
              aria-label={mutation.isPending ? "Stop agent response" : "Send message"}
            >
              {mutation.isPending ? <IconStopSquare /> : <IconSendUp />}
            </button>
          )}

          {mode === "text" ? (
            <button
              type="button"
              className="ws-icon-btn ws-mode-btn"
              disabled={!chatEnabled}
              onClick={switchToVoice}
              aria-label="Switch to voice mode"
            >
              <IconEqualizer />
            </button>
          ) : (
            <button
              type="button"
              className="ws-icon-btn ws-mode-btn"
              onClick={switchToText}
              aria-label="Switch to text mode"
            >
              <IconTextCursor />
            </button>
          )}
        </div>
      </div>
    </footer>
  );
}
