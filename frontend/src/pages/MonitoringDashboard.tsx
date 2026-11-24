import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getMonitoringSummary, getSampleEvaluation } from "../api/client";

export function MonitoringDashboard() {
  const monitoring = useQuery({ queryKey: ["monitoring-summary"], queryFn: getMonitoringSummary, refetchInterval: 5000 });
  const evaluation = useQuery({ queryKey: ["sample-evaluation"], queryFn: getSampleEvaluation, refetchInterval: 5000 });
  const data = monitoring.data;

  return (
    <main className="monitoring-page">
      <div className="monitoring-title"><div><p className="eyebrow">REAL LOCAL DATA</p><h1>Monitoring & checks</h1><p>Like a car dashboard: it shows what the app actually did.</p></div><Link to="/" className="monitoring-back">Back to app</Link></div>
      <section className="monitoring-cards">
        <article><span>Agent runs</span><strong>{data?.agent_runs ?? "—"}</strong></article>
        <article><span>Error rate</span><strong>{data ? `${data.error_rate}%` : "—"}</strong></article>
        <article><span>Average time</span><strong>{data ? `${data.average_duration_ms} ms` : "—"}</strong></article>
        <article><span>Tool calls</span><strong>{data?.tool_calls ?? "—"}</strong></article>
      </section>
      <section className="monitoring-section">
        <h2>Sample-file evaluation</h2>
        <p>These are repeatable file and preview checks, not made-up AI grades.</p>
        <div className="evaluation-score">{evaluation.data ? `${evaluation.data.average_score}/100` : "Loading…"}</div>
        {evaluation.data?.cases.map((sample) => <div className="monitoring-row" key={sample.name}><span>{sample.name}</span><span>{sample.score}/100 · {sample.passed ? "Pass" : "Needs attention"}</span></div>)}
      </section>
      <section className="monitoring-section">
        <h2>Recent agent runs</h2>
        {!data?.recent_runs.length && <p>No runs yet. Ask a question in a project, then return here.</p>}
        {data?.recent_runs.map((run) => <div className="monitoring-row" key={run.trace_id ?? `${run.query}-${run.duration_ms}`}><span>{run.query || "No query recorded"}<small>{run.source_format.toUpperCase()} · {run.tool_calls} tools</small></span><span>{run.status} · {run.duration_ms} ms</span></div>)}
      </section>
    </main>
  );
}
