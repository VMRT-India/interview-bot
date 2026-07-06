import { motion } from "framer-motion";
import { BrainCircuit, Gauge, MessagesSquare, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { StatCounter } from "../components/ui/StatCounter";
import { Testimonials } from "../components/ui/Testimonials";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/apiClient";
import type { PlatformStats } from "../lib/types";

const STEPS = [
  {
    icon: MessagesSquare,
    title: "Pick a track",
    body: "Technical, behavioral, HR — or paste a real job description for a role-specific session.",
  },
  {
    icon: BrainCircuit,
    title: "Interview live",
    body: "Questions stream in real time and adapt to your answers — no fixed script.",
  },
  {
    icon: Gauge,
    title: "Get scored feedback",
    body: "Every turn is evaluated on correctness, depth, and communication, with a full closing report.",
  },
];

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<PlatformStats | null>(null);

  useEffect(() => {
    api
      .get<PlatformStats>("/stats", false)
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  return (
    <Layout>
      {/* Hero */}
      <section className="flex flex-col items-center pt-10 text-center">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-4 flex items-center gap-2 rounded-full border border-white/15 bg-white/6 px-4 py-1.5 text-xs text-white/70"
        >
          <Sparkles size={14} className="text-[color:var(--color-accent-soft)]" />
          Adaptive AI interview simulation
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-6xl"
        >
          Practice interviews that actually push back
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-5 max-w-xl text-white/60"
        >
          No scripts. Follow-up questions adapt to what you actually say, difficulty scales to
          your level, and every answer gets structured, actionable feedback.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-8 flex gap-3"
        >
          <Button onClick={() => navigate(user ? "/interview/new" : "/signup")}>
            Start a mock interview
          </Button>
          <Button variant="ghost" onClick={() => navigate(user ? "/dashboard" : "/login")}>
            {user ? "Go to dashboard" : "Log in"}
          </Button>
        </motion.div>
      </section>

      {/* Live stats strip */}
      <section className="mt-20">
        <GlassCard className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <StatCounter value={stats?.total_users ?? 0} label="Registered candidates" />
          <StatCounter value={stats?.total_sessions ?? 0} label="Interviews started" />
          <StatCounter value={stats?.completed_sessions ?? 0} label="Interviews completed" />
          <StatCounter
            value={stats?.avg_score ? Math.round(stats.avg_score * 10) : 0}
            suffix="%"
            label="Avg. candidate score"
          />
        </GlassCard>
      </section>

      {/* About */}
      <section className="mt-24 text-center">
        <h2 className="text-2xl font-semibold text-white sm:text-3xl">
          Built to feel like a real interviewer
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-white/55">
          Behind the chat is a retrieval-grounded question engine and a per-turn evaluator —
          tracking your confidence, knowledge gaps, and communication quality as the interview
          progresses, and closing every session with a proper, professional wrap-up.
        </p>
      </section>

      {/* How it works */}
      <section className="mt-16 grid gap-6 sm:grid-cols-3">
        {STEPS.map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
          >
            <GlassCard hover className="h-full">
              <step.icon className="text-[color:var(--color-accent-soft)]" size={26} />
              <h3 className="mt-4 font-medium text-white">{step.title}</h3>
              <p className="mt-2 text-sm text-white/55">{step.body}</p>
            </GlassCard>
          </motion.div>
        ))}
      </section>

      {/* Testimonials */}
      <section className="mt-24">
        <h2 className="mb-10 text-center text-2xl font-semibold text-white sm:text-3xl">
          What candidates say
        </h2>
        <Testimonials />
      </section>
    </Layout>
  );
}
