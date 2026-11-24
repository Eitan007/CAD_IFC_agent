import { useMutation } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { sendChat } from "../api/client";
import type { ChatResponsePayload, PipelineStatus } from "../api/types";
import { useConversationStore } from "../stores/conversationStore";
import { useUiStore } from "../stores/uiStore";
import { entranceTransition, softPress, stateTransition } from "../utils/motion";
import { IconSendUp, IconStopSquare } from "./WorkspaceIcons";

type Props = {
  projectId: string;
  chatEnabled: boolean;
  pipelineStatus?: PipelineStatus;
  pipelineError?: string | null;
};

export function WorkspaceComposer({
  projectId,
  chatEnabled,
  pipelineStatus,
  pipelineError,
}: Props) {
  const selectedElementId = useUiStore((s) => s.selectedElementId);
  const storeyFilter = useUiStore((s) => s.storeyFilter);
  const typeFilter = useUiStore((s) => s.typeFilter);
  const appendMessage = useConversationStore((s) => s.appendMessage);
  const replacePendingMessage = useConversationStore((s) => s.replacePendingMessage);
  const messages = useConversationStore((s) => s.messages);

  const [input, setInput] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const composerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const el = composerRef.current;
    if (!el) return;

    const updateHeight = () => {
      const rect = el.getBoundingClientRect();
      document.documentElement.style.setProperty("--composer-bottom", `${rect.bottom}px`);
    };

    updateHeight();

    const observer = new ResizeObserver(() => {
      updateHeight();
    });
    observer.observe(el);

    return () => {
      observer.disconnect();
      document.documentElement.style.removeProperty("--composer-bottom");
    };
  }, []);

  const mutation = useMutation<ChatResponsePayload, unknown, string>(
    useMemo(
      () => ({
        mutationFn: async (text: string) => {
          abortRef.current?.abort();
          const controller = new AbortController();
          abortRef.current = controller;

          let message = text;
          const ctx: string[] = [];
          if (selectedElementId) ctx.push(`Selected model element ID: ${selectedElementId}`);
          if (storeyFilter) ctx.push(`Focus storey: ${storeyFilter}`);
          if (typeFilter) ctx.push(`Focus component type: ${typeFilter}`);
          if (ctx.length) message = `${ctx.join(" | ")}\n\n${text}`;

          // React Query may run onMutate before this function, so remove the
          // just-added question if it is already in the store. The API adds
          // `message` as the current turn itself.
          const history = messages
            .filter((item) => item.id !== "welcome" && item.id !== "pending-assistant" && !item.id.startsWith("err-"))
            .map((item) => ({ role: item.role, content: item.text }));
          const lastHistoryItem = history.at(-1);
          if (lastHistoryItem?.role === "user" && lastHistoryItem.content === text) {
            history.pop();
          }

          return sendChat(
            projectId,
            {
              message,
              selected_element: selectedElementId,
              history: history.slice(-12),
            },
            controller.signal,
          );
        },
        onMutate: (text) => {
          appendMessage({ role: "user", text });
          appendMessage({ role: "assistant", text: "Thinking…", id: "pending-assistant" });
          setInput("");
        },
        onSuccess: (data) => {
          replacePendingMessage({
            id: `assistant-${Date.now()}`,
            role: "assistant",
            text: data.answer,
            refs: data.references ?? [],
          });
        },
        onError: (err: unknown) => {
          if (err instanceof Error && err.name === "AbortError") {
            replacePendingMessage(null);
            return;
          }
          const msg = err instanceof Error ? err.message : String(err);
          replacePendingMessage({ id: `err-${Date.now()}`, role: "assistant", text: `Request failed: ${msg}` });
        },
        onSettled: () => {
          abortRef.current = null;
        },
      }),
      [projectId, selectedElementId, storeyFilter, typeFilter, appendMessage, replacePendingMessage, messages],
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

  return (
    <motion.footer
      ref={composerRef}
      initial={{ opacity: 0, x: "-50%", y: 20, scale: 0.95 }}
      animate={{ opacity: 1, x: "-50%", y: 0, scale: 1 }}
      transition={entranceTransition}
      className="ws-composer"
    >
      <div className="ws-composer-inner glass-card">
        <motion.textarea
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={stateTransition}
          className="ws-composer-input"
          placeholder={
            chatEnabled
              ? "Ask about this model…"
              : pipelineStatus === "processing" || pipelineStatus === "queued"
                ? "Preparing your model…"
                : pipelineError
                  ? `Pipeline error: ${pipelineError}`
                  : "Chat unlocks when your model is ready…"
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

        <div className="ws-composer-actions">
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
        </div>
      </div>
    </motion.footer>
  );
}
