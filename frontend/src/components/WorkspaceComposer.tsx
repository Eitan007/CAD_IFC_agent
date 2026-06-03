import { useMutation } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { sendChat } from "../api/client";
import type { ChatResponsePayload, PipelineStatus } from "../api/types";
import { useVoiceSession } from "../hooks/useVoiceSession";
import { useConversationStore } from "../stores/conversationStore";
import { useUiStore } from "../stores/uiStore";
import { entranceTransition, softPress, stateTransition } from "../utils/motion";
import { IconBack, IconEqualizer, IconSendUp, IconStopSquare } from "./WorkspaceIcons";
import { VoiceStringVisualizer } from "./VoiceStringVisualizer";
import type { ComposerMode } from "./WorkspaceComposer.types";

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

  const { room, connected, stringActive, error, connect, pause } = useVoiceSession(
    projectId,
    chatEnabled,
  );

  useEffect(() => {
    if (mode !== "voice" || !chatEnabled) return;
    void connect();
  }, [mode, chatEnabled, connect]);

  useEffect(() => {
    if (mode === "text" && connected) {
      void pause();
    }
  }, [mode, connected, pause]);

  const mutation = useMutation<ChatResponsePayload, unknown, string>(
    useMemo(
      () => ({
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
      }),
      [projectId, selectedElementId, storeyFilter, typeFilter, appendMessage],
    ),
  );

  const handleSendOrStop = useCallback(() => {
    if (mutation.isPending) {
      abortRef.current?.abort();
      mutation.reset();
      return;
    }
    if (!chatEnabled) return;
    const trimmed = input.trim();
    if (!trimmed) return;
    mutation.mutate(trimmed);
  }, [mutation, chatEnabled, input]);

  const switchToVoice = useCallback(() => {
    if (!chatEnabled) return;
    onModeChange("voice");
  }, [chatEnabled, onModeChange]);

  const switchToText = useCallback(() => {
    onModeChange("text");
  }, [onModeChange]);

  return (
    <motion.footer
      initial={{ opacity: 0, x: "-50%", y: 20, scale: 0.95 }}
      animate={{ opacity: 1, x: "-50%", y: 0, scale: 1 }}
      transition={entranceTransition}
      className={`ws-composer ${mode === "voice" ? "ws-composer-voice" : ""}`}
    >
      <div className="ws-composer-inner glass-card">
        <AnimatePresence mode="wait">
          {mode === "text" ? (
            <motion.textarea
              key="text-input"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={stateTransition}
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
            <motion.div
              key="voice-input"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={stateTransition}
              className="ws-composer-voice-strip"
            >
              <VoiceStringVisualizer room={room} active={stringActive} variant="compact" />
              {error && <p className="ws-composer-voice-err">{error}</p>}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="ws-composer-actions">
          {mode === "text" && (
            <motion.button
              whileTap={softPress}
              transition={stateTransition}
              type="button"
              className={`ws-icon-btn ws-send-btn ${mutation.isPending ? "is-stop" : ""}`}
              disabled={!chatEnabled}
              onClick={handleSendOrStop}
              aria-label={mutation.isPending ? "Stop agent response" : "Send message"}
            >
              {mutation.isPending ? <IconStopSquare /> : <IconSendUp />}
            </motion.button>
          )}

          {mode === "text" ? (
            <motion.button
              whileTap={softPress}
              transition={stateTransition}
              type="button"
              className="ws-icon-btn ws-mode-btn"
              disabled={!chatEnabled}
              onClick={switchToVoice}
              aria-label="Switch to voice mode"
            >
              <IconEqualizer />
            </motion.button>
          ) : (
            <motion.button
              whileTap={softPress}
              transition={stateTransition}
              type="button"
              className="ws-icon-btn ws-mode-btn"
              onClick={switchToText}
              aria-label="Switch to text mode"
            >
              <IconBack />
            </motion.button>
          )}
        </div>
      </div>
    </motion.footer>
  );
}
