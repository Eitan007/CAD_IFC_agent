import { useEffect, useRef } from "react";
import { useConversationStore } from "../stores/conversationStore";
import { ChatMarkdown } from "./ChatMarkdown";

export function ConversationPanel() {
  const messages = useConversationStore((s) => s.messages);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <aside className="ws-conversation glass-card" aria-label="Conversation">
      <div className="ws-conversation-fade ws-conversation-fade-top" aria-hidden />
      <div className="ws-conversation-scroll" ref={scrollRef}>
        {messages.map((m) => (
          <div
            key={m.id}
            className={`ws-bubble-row ${m.role === "user" ? "ws-bubble-row-user" : "ws-bubble-row-ai"}`}
          >
            <div className={m.role === "user" ? "ws-bubble ws-bubble-user" : "ws-bubble ws-bubble-ai"}>
              <span className="ws-bubble-tag">{m.role === "user" ? "USER CHAT" : "AI CHAT"}</span>
              <div className="ws-bubble-body">
                {m.role === "assistant" ? (
                  <ChatMarkdown text={m.text} className="ws-bubble-text chat-markdown" />
                ) : (
                  <p className="ws-bubble-text">{m.text}</p>
                )}
                {!!m.refs?.length && (
                  <div className="ws-bubble-refs">
                    {m.refs.map((r, i) => (
                      <span key={`${r.kind}-${i}`} className="ws-ref-pill">
                        {r.kind}
                        {r.detail ? `: ${r.detail}` : ""}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="ws-conversation-fade ws-conversation-fade-bottom" aria-hidden />
      <div className="glass-card-dots" aria-hidden />
    </aside>
  );
}
