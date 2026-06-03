import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { entranceTransition, softEntrance, softPress, stateTransition } from "../utils/motion";
import { ChatPanel } from "./ChatPanel";
import { VoicePanel } from "./VoicePanel";

type Mode = "text" | "voice";

type Props = {
  projectId: string;
  chatEnabled: boolean;
};

export function AgentPanel({ projectId, chatEnabled }: Props) {
  const [mode, setMode] = useState<Mode>("text");

  return (
    <motion.section
      className="glass-panel chat-pane agent-panel"
      initial="hidden"
      animate="show"
      variants={softEntrance}
      transition={entranceTransition}
      style={{ minHeight: 0, flex: 1, display: "flex", flexDirection: "column" }}
    >
      <div className="agent-mode-tabs">
        <motion.button
          type="button"
          className={`agent-mode-tab ${mode === "text" ? "active" : ""}`}
          whileTap={softPress}
          onClick={() => setMode("text")}
        >
          Text
        </motion.button>
        <motion.button
          type="button"
          className={`agent-mode-tab ${mode === "voice" ? "active" : ""}`}
          whileTap={softPress}
          onClick={() => setMode("voice")}
        >
          Voice
        </motion.button>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          className="agent-panel-mode"
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.98 }}
          transition={stateTransition}
        >
          {mode === "text" ? (
            <ChatPanel projectId={projectId} chatEnabled={chatEnabled} embedded />
          ) : (
            <VoicePanel projectId={projectId} voiceEnabled={chatEnabled} />
          )}
        </motion.div>
      </AnimatePresence>
    </motion.section>
  );
}
