import { useState } from "react";
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
    <section className="glass-panel chat-pane agent-panel" style={{ minHeight: 0, flex: 1, display: "flex", flexDirection: "column" }}>
      <div className="agent-mode-tabs">
        <button
          type="button"
          className={`agent-mode-tab ${mode === "text" ? "active" : ""}`}
          onClick={() => setMode("text")}
        >
          Text
        </button>
        <button
          type="button"
          className={`agent-mode-tab ${mode === "voice" ? "active" : ""}`}
          onClick={() => setMode("voice")}
        >
          Voice
        </button>
      </div>

      {mode === "text" ? (
        <ChatPanel projectId={projectId} chatEnabled={chatEnabled} embedded />
      ) : (
        <VoicePanel projectId={projectId} voiceEnabled={chatEnabled} />
      )}
    </section>
  );
}
