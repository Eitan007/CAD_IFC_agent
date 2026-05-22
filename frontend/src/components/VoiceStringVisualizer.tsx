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

function buildPath(amplitude: number, phase: number): string {
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
    const y = BASELINE - amplitude * (main * (1 + flow) + leftBump);
    pts.push(i === 0 ? `M ${x.toFixed(1)} ${y.toFixed(1)}` : `L ${x.toFixed(1)} ${y.toFixed(1)}`);
  }
  return pts.join(" ");
}

function peakPoint(amplitude: number): { x: number; y: number } {
  return { x: W / 2, y: BASELINE - amplitude };
}

export function VoiceStringVisualizer({ room, active, variant = "card" }: Props) {
  const pathRef = useRef<SVGPathElement>(null);
  const beadRef = useRef<SVGCircleElement>(null);
  const glowPathRef = useRef<SVGPathElement>(null);
  const smoothRef = useRef(0);
  const phaseRef = useRef(0);
  const rafRef = useRef(0);

  useEffect(() => {
    const tick = (t: number) => {
      const raw = active ? combinedAudioLevel(room) : 0;
      const idle = active ? 0 : 0.04 + 0.03 * Math.sin(t * 0.0012);
      const target = active ? Math.max(raw, 0.02) : idle;
      smoothRef.current += (target - smoothRef.current) * 0.18;

      phaseRef.current += active ? 0.045 + smoothRef.current * 0.08 : 0.018;
      const amp =
        MIN_AMP + smoothRef.current * (MAX_AMP - MIN_AMP);
      const d = buildPath(amp, phaseRef.current);
      const peak = peakPoint(amp);

      pathRef.current?.setAttribute("d", d);
      glowPathRef.current?.setAttribute("d", d);
      beadRef.current?.setAttribute("cx", String(peak.x));
      beadRef.current?.setAttribute("cy", String(peak.y));

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
          <filter id="voiceBeadGlow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path
          ref={glowPathRef}
          className="voice-string-glow"
          fill="none"
          d={buildPath(MIN_AMP, 0)}
        />
        <path
          ref={pathRef}
          className="voice-string-line"
          fill="none"
          d={buildPath(MIN_AMP, 0)}
        />
        <circle
          ref={beadRef}
          className="voice-string-bead"
          cx={W / 2}
          cy={BASELINE - MIN_AMP}
          r="5"
          filter="url(#voiceBeadGlow)"
        />
      </svg>
    </div>
  );
}
