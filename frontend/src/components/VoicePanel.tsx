import { useEffect } from "react";
import { motion } from "framer-motion";
import { useVoiceSession } from "../hooks/useVoiceSession";
import { useUiStore } from "../stores/uiStore";
import { entranceTransition, softContainer, softItem, softPress } from "../utils/motion";
import { VoiceStringVisualizer } from "./VoiceStringVisualizer";


type Props = {
  projectId: string;
  voiceEnabled: boolean;
};

const STATUS: Record<string, string> = {
  idle: "Start a voice session with Bimi.",
  connecting: "Connecting to voice room…",
  listening: "Listening — ask about your building model.",
  speaking: "Bimi is speaking…",
  error: "Voice session needs attention.",
};

export function VoicePanel({ projectId, voiceEnabled }: Props) {
  const selectedElementId = useUiStore((s) => s.selectedElementId);
  const { room, connected, voiceState, stringActive, error, connect, disconnect } = useVoiceSession(
    projectId,
    voiceEnabled,
  );

  useEffect(() => {
    if (voiceEnabled && !connected && voiceState !== "connecting" && voiceState !== "error") {
      void connect();
    }
  }, [voiceEnabled, connected, voiceState, connect]);

  const statusLine =
    voiceState === "error" && error
      ? error
      : (STATUS[voiceState] ?? STATUS.idle);

  return (
    <motion.div className="voice-pane" variants={softContainer} initial="hidden" animate="show">
      <motion.div variants={softItem} transition={entranceTransition} style={{ padding: "0.65rem 0.75rem", borderBottom: "1px solid color-mix(in srgb, var(--cyan) 20%, transparent)" }}>
        <div style={{ fontWeight: 700 }}>Voice assistant</div>
        <div className="muted" style={{ marginTop: "0.25rem", fontSize: "0.85rem" }}>
          Same BIM agent as text chat — powered by LiveKit + backend tools.
        </div>
        {selectedElementId && (
          <div className="muted" style={{ marginTop: "0.35rem", fontSize: "0.82rem" }}>
            Selected element: <code>{selectedElementId}</code>
          </div>
        )}
      </motion.div>

      <motion.div className="voice-stage" variants={softItem} transition={entranceTransition}>
        <VoiceStringVisualizer room={room} active={stringActive} />

        <p className="voice-status">{statusLine}</p>
        {error && voiceState !== "error" && (
          <p className="voice-error" role="alert">
            {error}
          </p>
        )}
      </motion.div>

      <motion.div className="voice-actions" variants={softItem} transition={entranceTransition}>
        {!connected ? (
          <motion.button
            type="button"
            className="btn-voice"
            whileTap={softPress}
            disabled={!voiceEnabled || voiceState === "connecting"}
            onClick={() => void connect()}
          >
            {voiceEnabled ? "Start voice" : "Voice unlocks after pipeline"}
          </motion.button>
        ) : (
          <motion.button type="button" className="btn-voice btn-voice-end" whileTap={softPress} onClick={() => void disconnect()}>
            End session
          </motion.button>
        )}
      </motion.div>
    </motion.div>
  );
}
