import type { Room } from "livekit-client";
import { useEffect, useRef } from "react";

type Props = {
  room: Room | null;
  active: boolean;
  variant?: "card" | "compact";
};

const W = 400;
const H = 200;
const BASELINE = H * 0.72;
const MIN_AMP = 6;
const MAX_AMP = 72;

function combinedAudioLevel(room: Room | null): number {
  if (!room) return 0;
  let peak = room.localParticipant.audioLevel ?? 0;
  room.remoteParticipants.forEach((p) => {
    peak = Math.max(peak, p.audioLevel ?? 0);
  });
  return peak;
}

function buildPath(amplitude: number, phase: number, frequencyData: Uint8Array | null): string {
  const cx = W / 2;
  const steps = 64;
  const pts: string[] = [];

  for (let i = 0; i <= steps; i++) {
    const x = (i / steps) * W;
    const nx = (x - cx) / (W * 0.2);
    const main = Math.exp(-nx * nx * 1.15);
    const flow = 0.12 * Math.sin(nx * 2.8 + phase) * main;
    const leftBump =
      0.28 *
      Math.exp(-Math.pow((x - cx * 0.62) / (W * 0.14), 2));
    
    // Multi-point reactivity: add hash-based noise at different positions
    const posHash = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
    const posNoise = (posHash - Math.floor(posHash)) - 0.5;
    let reactivePoint = 0.18 * posNoise * Math.sin(phase + i * 0.8) * main;
    
    // Add frequency-based reactivity: map frequency bins to string positions
    if (frequencyData) {
      const freqBin = Math.floor((i / steps) * frequencyData.length);
      const clipped = Math.max(0, Math.min(frequencyData.length - 1, freqBin));
      const freqReactivity = (frequencyData[clipped] / 255) * 0.3;
      reactivePoint += freqReactivity * main;
    }
    
    const y = BASELINE - amplitude * (main * (1 + flow) + leftBump + reactivePoint);
    pts.push(i === 0 ? `M ${x.toFixed(1)} ${y.toFixed(1)}` : `L ${x.toFixed(1)} ${y.toFixed(1)}`);
  }
  return pts.join(" ");
}

export function VoiceStringVisualizer({ room, active, variant = "card" }: Props) {
  const pathRef = useRef<SVGPathElement>(null);
  const glowPathRef = useRef<SVGPathElement>(null);
  const smoothRef = useRef(0);
  const phaseRef = useRef(0);
  const rafRef = useRef(0);
  
  // Audio analysis for frequency-based reactivity
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const freqDataRef = useRef<Uint8Array | null>(null);

  // Setup Web Audio API when audio element becomes available
  useEffect(() => {
    if (!active) return;
    
    const audioEl = document.querySelector("#bim-agent-audio") as HTMLAudioElement;
    if (!audioEl) return;
    
    try {
      const audioCtx = audioContextRef.current || new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioCtx;
      
      if (audioCtx.state === "suspended") {
        audioCtx.resume();
      }
      
      if (!analyserRef.current) {
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        
        try {
          if (audioEl.srcObject instanceof MediaStream) {
            const source = audioCtx.createMediaStreamSource(audioEl.srcObject);
            source.connect(analyser);
            // We don't connect to destination because the audioEl is already playing the stream.
            // This also avoids the "Applying volume or mute status is not supported" warning.
          } else {
            const source = audioCtx.createMediaElementSource(audioEl);
            source.connect(analyser);
            analyser.connect(audioCtx.destination);
          }
        } catch (e) {
          // Source already created or not available
        }
        
        analyserRef.current = analyser;
        freqDataRef.current = new Uint8Array(analyser.frequencyBinCount);
      }
    } catch (err) {
      console.error("Audio context setup failed:", err);
    }
    
    return () => {
      // Keep context alive for reconnects
    };
  }, [active]);

  useEffect(() => {
    const tick = (t: number) => {
      const raw = active ? combinedAudioLevel(room) : 0;
      const idle = active ? 0 : 0.04 + 0.03 * Math.sin(t * 0.0012);
      const target = active ? Math.max(raw, 0.02) : idle;
      smoothRef.current += (target - smoothRef.current) * 0.29;

      phaseRef.current += active ? 0.072 + smoothRef.current * 0.128 : 0.018;
      const amp =
        MIN_AMP + smoothRef.current * (MAX_AMP - MIN_AMP);
      
      // Get frequency data if analyser is available
      if (analyserRef.current && freqDataRef.current && active) {
        analyserRef.current.getByteFrequencyData(freqDataRef.current);
      }
      
      const d = buildPath(amp, phaseRef.current, freqDataRef.current);

      pathRef.current?.setAttribute("d", d);
      glowPathRef.current?.setAttribute("d", d);

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [room, active]);

  const rootClass = [
    variant === "compact" ? "voice-string-compact" : "voice-string-card",
    active ? "voice-string-card-active" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rootClass} aria-hidden="true">
      <div className="voice-string-grid" />
      <svg className="voice-string-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="voiceStringStroke" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#4d9fff" stopOpacity="0" />
            <stop offset="18%" stopColor="#5eb0ff" stopOpacity="0.35" />
            <stop offset="42%" stopColor="#7ec8ff" stopOpacity="0.85" />
            <stop offset="50%" stopColor="#a8dcff" stopOpacity="1" />
            <stop offset="58%" stopColor="#7ec8ff" stopOpacity="0.85" />
            <stop offset="82%" stopColor="#5eb0ff" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#4d9fff" stopOpacity="0" />
          </linearGradient>
          <filter id="voiceStringGlow" x="-20%" y="-80%" width="140%" height="260%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path
          ref={glowPathRef}
          className="voice-string-glow"
          fill="none"
          d={buildPath(MIN_AMP, 0, null)}
        />
        <path
          ref={pathRef}
          className="voice-string-line"
          fill="none"
          d={buildPath(MIN_AMP, 0, null)}
        />
      </svg>
    </div>
  );
}
