import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { GlassCard } from "../components/ui/GlassCard";
import { ScoreBadge } from "../components/ui/ScoreBadge";
import { api } from "../lib/apiClient";
import type { SessionDetail } from "../lib/types";

export default function SessionReportPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    api
      .get<SessionDetail>(`/sessions/${sessionId}`)
      .then(setDetail)
      .catch(() => setError("Could not load this session."));
  }, [sessionId]);

  if (error) {
    return (
      <Layout showFooter={false}>
        <p className="text-[color:var(--color-bad)]">{error}</p>
      </Layout>
    );
  }

  if (!detail) {
    return (
      <Layout showFooter={false}>
        <p className="text-white/50">Loading…</p>
      </Layout>
    );
  }

  return (
    <Layout showFooter={false}>
      <Link to="/dashboard" className="text-sm text-[color:var(--color-accent-soft)]">
        ← Back to dashboard
      </Link>

      <div className="mt-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">
            {detail.interview_type} interview
          </h1>
          <p className="text-sm text-white/45">
            {new Date(detail.started_at).toLocaleString()} · {detail.status}
          </p>
        </div>
        {detail.total_score !== null && <ScoreBadge score={detail.total_score} size="lg" />}
      </div>

      {detail.overall_summary ? (
        <div className="mt-8 grid gap-5 lg:grid-cols-2">
          <GlassCard>
            <h2 className="font-medium text-white">Summary</h2>
            <p className="mt-2 text-sm text-white/65">{detail.overall_summary}</p>
            <div className="mt-4 inline-block rounded-full border border-white/15 bg-white/6 px-3 py-1 text-xs text-white/70">
              Hire signal: {detail.hire_signal}
            </div>
          </GlassCard>

          <GlassCard>
            <h2 className="font-medium text-white">Strengths</h2>
            <ul className="mt-2 list-disc pl-4 text-sm text-white/65">
              {detail.top_strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </GlassCard>

          <GlassCard>
            <h2 className="font-medium text-white">Key gaps</h2>
            <ul className="mt-2 list-disc pl-4 text-sm text-white/65">
              {detail.key_gaps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </GlassCard>

          <GlassCard>
            <h2 className="font-medium text-white">Recommendations</h2>
            <ul className="mt-2 list-disc pl-4 text-sm text-white/65">
              {detail.recommendations.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </GlassCard>
        </div>
      ) : (
        <p className="mt-8 text-sm text-white/45">
          {detail.status === "ACTIVE"
            ? "This interview is still in progress — the full report appears once it's closed."
            : "No narrative report was saved for this session — showing per-turn scores only."}
        </p>
      )}

      <div className="mt-10">
        <h2 className="mb-3 font-medium text-white">Turn-by-turn scores</h2>
        <div className="flex flex-col gap-3">
          {detail.turn_scores.map((t) => (
            <GlassCard key={t.id} tight className="flex items-start gap-4">
              <ScoreBadge score={t.score} size="sm" />
              <div className="text-sm text-white/70">
                <div className="text-xs text-white/40">Turn {t.turn_number}</div>
                <p className="mt-1">
                  <span className="text-white/50">Strengths:</span> {t.strengths}
                </p>
                <p className="mt-1">
                  <span className="text-white/50">Weaknesses:</span> {t.weaknesses}
                </p>
                <p className="mt-1">
                  <span className="text-white/50">Improve:</span> {t.improvement}
                </p>
              </div>
            </GlassCard>
          ))}
          {detail.turn_scores.length === 0 && (
            <p className="text-sm text-white/45">No scored turns yet.</p>
          )}
        </div>
      </div>
    </Layout>
  );
}
