import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { sendChat } from "../api/client";
import type { ChatReference } from "../api/types";
import { useUiStore } from "../stores/uiStore";
import { ChatMarkdown } from "./ChatMarkdown";

type Msg = {
  role: "user" | "assistant";
  text: string;
  refs?: ChatReference[];
};

type Props = {
  projectId: string;
  chatEnabled: boolean;
  /** When true, omit outer glass shell (used inside AgentPanel). */
  embedded?: boolean;
};

export function ChatPanel({ projectId, chatEnabled, embedded = false }: Props) {
  const selectedElementId = useUiStore((s) => s.selectedElementId);
  const storeyFilter = useUiStore((s) => s.storeyFilter);
  const typeFilter = useUiStore((s) => s.typeFilter);

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      text: "Ask questions about quantities, cost, schedule, or compliance. Click the model to attach an IFC express ID to your prompt.",
    },
  ]);

  const hint = useMemo(() => {
    const bits: string[] = [];
    if (storeyFilter) bits.push(`storey=${storeyFilter}`);
    if (typeFilter) bits.push(`type=${typeFilter}`);
    return bits.length ? `Filters (chat context): ${bits.join(", ")}` : null;
  }, [storeyFilter, typeFilter]);

  const mutation = useMutation({
    mutationFn: async (payload: { text: string }) => {
      let message = payload.text;
      const ctx: string[] = [];
      if (selectedElementId) ctx.push(`Selected IFC express ID: ${selectedElementId}`);
      if (storeyFilter) ctx.push(`Focus storey: ${storeyFilter}`);
      if (typeFilter) ctx.push(`Focus component type: ${typeFilter}`);
      if (ctx.length) message = `${ctx.join(" | ")}\n\n${payload.text}`;

      return sendChat(projectId, {
        message,
        selected_element: selectedElementId,
      });
    },
    onMutate: async ({ text }) => {
      setMessages((prev) => [...prev, { role: "user", text }]);
      setInput("");
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.answer,
          refs: data.references ?? [],
        },
      ]);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages((prev) => [...prev, { role: "assistant", text: `Request failed: ${msg}` }]);
    },
  });

  const handleSend = () => {
    if (!chatEnabled || mutation.isPending) return;
    const trimmed = input.trim();
    if (!trimmed) return;
    mutation.mutate({ text: trimmed });
  };

  const shellClass = embedded ? "chat-pane-embedded" : "glass-panel chat-pane";

  return (
    <section className={shellClass} style={{ minHeight: 0, flex: 1, display: "flex", flexDirection: "column" }}>
      <div style={{ padding: "0.65rem 0.75rem", borderBottom: "1px solid color-mix(in srgb, var(--accent) 15%, transparent)" }}>
        <div style={{ fontWeight: 700 }}>Knowledge graph QA</div>
        <div className="muted" style={{ marginTop: "0.25rem", fontSize: "0.85rem" }}>
          Powered by backend tools + LLM (no raw IFC in model context).
        </div>
        {hint && (
          <div className="muted" style={{ marginTop: "0.35rem", fontSize: "0.82rem" }}>
            {hint}
          </div>
        )}
      </div>

      <div className="chat-scroll">
        {messages.map((m, idx) => (
          <div key={`${idx}-${m.role}`} className="chat-row">
            <div className={m.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"}>
              {m.role === "assistant" ? (
                <ChatMarkdown text={m.text} />
              ) : (
                m.text
              )}
              {!!m.refs?.length && (
                <div style={{ marginTop: "0.55rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                  {m.refs.map((r, i) => (
                    <span key={`${r.kind}-${i}`} className="pill" style={{ fontSize: "0.72rem" }}>
                      {r.kind}
                      {r.detail ? `: ${r.detail}` : ""}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="chat-input-row">
        <textarea
          placeholder={
            chatEnabled
              ? "Ask questions"
              : "Chat unlocks after the pipeline completes."
          }
          disabled={!chatEnabled || mutation.isPending}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        <button type="button" className="btn-primary" disabled={!chatEnabled || mutation.isPending} onClick={handleSend}>
          Send
        </button>
      </div>
    </section>
  );
}
