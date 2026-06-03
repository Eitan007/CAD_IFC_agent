import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useConversationStore } from "../stores/conversationStore";
import { entranceTransition, softContainer } from "../utils/motion";
import { ChatMarkdown } from "./ChatMarkdown";

export function ConversationPanel() {
  const messages = useConversationStore((s) => s.messages);
  const scrollRef = useRef<HTMLDivElement>(null);
  const hasMessages = messages.length > 0;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <aside className={`ws-conversation glass-card ${hasMessages ? "has-messages" : "no-messages"}`} aria-label="Conversation">
      <motion.div
        className="ws-conversation-scroll"
        ref={scrollRef}
        variants={softContainer}
        initial="hidden"
        animate="show"
      >
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div
              key={m.id}
              initial="hidden"
              animate="show"
              exit="exit"
              variants={{
                hidden: { opacity: 0, y: 20 },
                show: { opacity: 1, y: 0 },
                exit: { opacity: 0, y: 8 },
              }}
              transition={{ ...entranceTransition, delay: Math.min(i, 4) * 0.1 }}
              className={`ws-bubble-row ${m.role === "user" ? "ws-bubble-row-user" : "ws-bubble-row-ai"}`}
            >
              <div className={m.role === "user" ? "ws-bubble ws-bubble-user" : "ws-bubble ws-bubble-ai"}>
                <span className="ws-bubble-tag">{m.role === "user" ? "You" : "BIMI"}</span>
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
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>
      <div className="glass-card-dots" aria-hidden />
    </aside>
  );
}
