import { Lightbulb } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { ScoreBadge } from "../components/ui/ScoreBadge";
import { api } from "../lib/apiClient";
import type { SessionDetail, SessionRead } from "../lib/types";

export default function Dashboard() {
  const [sessions, setSessions] = useState<SessionRead[] | null>(null);
  const [improvementNotes, setImprovementNotes] = useState<string[]>([]);

  useEffect(() => {
    api.get<SessionRead[]>("/sessions").then(setSessions);
  }, []);

  const completed = useMemo(
    () => (sessions ?? []).filter((s) => s.status === "COMPLETED" && s.total_score !== null),
    [sessions]
  );

  useEffect(() => {
    if (completed.length === 0) return;
    const recent = completed.slice(0, 2);
    Promise.all(recent.map((s) => api.get<SessionDetail>(`/sessions/${s.id}`)))
      .then((details) => {
        const notes = details
          .flatMap((d) => d.turn_scores)
          .flatMap((t) => [t.improvement, t.weaknesses])
          .filter(Boolean)
          .slice(0, 5);
        setImprovementNotes(notes);
      })
      .catch(() => setImprovementNotes([]));
  }, [completed]);

  const avgScore =
    completed.length > 0
      ? completed.reduce((sum, s) => sum + (s.total_score ?? 0), 0) / completed.length
      : null;
  const bestScore =
    completed.length > 0 ? Math.max(...completed.map((s) => s.total_score ?? 0)) : null;
  const totalMinutes = completed.reduce((sum, s) => {
    if (!s.ended_at) return sum;
    return sum + (new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()) / 60000;
  }, 0);

  const chartData = [...completed]
    .reverse()
    .map((s, i) => ({ turn: i + 1, score: s.total_score }));

  return (
    <Layout showFooter={false}>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Your dashboard</h1>
        <Link to="/interview/new">
          <Button>New interview</Button>
        </Link>
      </div>

      <div className="mt-6 grid gap-5 sm:grid-cols-4">
        <GlassCard tight>
          <div className="text-xs text-white/50">Sessions completed</div>
          <div className="mt-1 text-2xl font-semibold text-white">{completed.length}</div>
        </GlassCard>
        <GlassCard tight>
          <div className="text-xs text-white/50">Average score</div>
          <div className="mt-1 text-2xl font-semibold text-white">
            {avgScore !== null ? avgScore.toFixed(1) : "—"}
          </div>
        </GlassCard>
        <GlassCard tight>
          <div className="text-xs text-white/50">Best score</div>
          <div className="mt-1 text-2xl font-semibold text-white">
            {bestScore !== null ? bestScore.toFixed(1) : "—"}
          </div>
        </GlassCard>
        <GlassCard tight>
          <div className="text-xs text-white/50">Time practiced</div>
          <div className="mt-1 text-2xl font-semibold text-white">
            {Math.round(totalMinutes)}m
          </div>
        </GlassCard>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-3">
        <GlassCard className="lg:col-span-2">
          <h2 className="font-medium text-white">Score trend</h2>
          {chartData.length >= 2 ? (
            <div className="mt-4 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="turn" stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <YAxis domain={[0, 10]} stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      background: "#0d0f1a",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#0a84ff"
                    strokeWidth={2}
                    dot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="mt-4 text-sm text-white/45">
              Complete at least two interviews to see your trend.
            </p>
          )}
        </GlassCard>

        <GlassCard>
          <div className="flex items-center gap-2">
            <Lightbulb size={18} className="text-[color:var(--color-warn)]" />
            <h2 className="font-medium text-white">Improvement partner</h2>
          </div>
          {improvementNotes.length > 0 ? (
            <ul className="mt-4 space-y-3 text-sm text-white/65">
              {improvementNotes.map((note, i) => (
                <li key={i} className="border-l-2 border-white/15 pl-3">
                  {note}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-white/45">
              Finish an interview to get personalized focus areas here.
            </p>
          )}
        </GlassCard>
      </div>

      <div className="mt-8">
        <h2 className="mb-3 font-medium text-white">Recent sessions</h2>
        <div className="flex flex-col gap-3">
          {sessions === null && <p className="text-sm text-white/45">Loading…</p>}
          {sessions?.length === 0 && (
            <p className="text-sm text-white/45">No interviews yet — start your first one.</p>
          )}
          {sessions?.map((s) => (
            <Link
              key={s.id}
              to={s.status === "ACTIVE" ? `/interview/${s.id}` : `/sessions/${s.id}`}
            >
              <GlassCard tight hover className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-white">{s.interview_type}</div>
                  <div className="text-xs text-white/45">
                    {new Date(s.started_at).toLocaleString()} · {s.status}
                  </div>
                </div>
                {s.total_score !== null ? (
                  <ScoreBadge score={s.total_score} size="sm" />
                ) : (
                  <span className="text-xs text-white/40">In progress</span>
                )}
              </GlassCard>
            </Link>
          ))}
        </div>
      </div>
    </Layout>
  );
}
