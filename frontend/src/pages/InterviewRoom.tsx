import { Clock } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChatBubble } from "../components/interview/ChatBubble";
import { ChatComposer } from "../components/interview/ChatComposer";
import { LiveMediaControls } from "../components/interview/LiveMediaControls";
import { Layout } from "../components/layout/Layout";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { useElapsedTimer } from "../hooks/useElapsedTimer";
import { useInterviewSocket } from "../hooks/useInterviewSocket";
import { api } from "../lib/apiClient";
import type { SessionRead } from "../lib/types";

export default function InterviewRoom() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { status, draftQuestion, turns, errorMessage, endMessage, sendAnswer, disconnect } =
    useInterviewSocket(sessionId!);
  const [startedAt, setStartedAt] = useState<number>(Date.now());
  const [targetMinutes, setTargetMinutes] = useState<number | null>(null);
  const [closing, setClosing] = useState(false);
  const [terminating, setTerminating] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function handleTerminate() {
    if (!sessionId || terminating) return;
    const confirmed = window.confirm(
      "End this interview now? It can't be resumed, but you'll still get a score and " +
        "report for what you've completed so far."
    );
    if (!confirmed) return;

    setTerminating(true);
    disconnect();
    try {
      await api.post(`/sessions/${sessionId}/close?terminated=true`);
    } finally {
      navigate(`/sessions/${sessionId}`, { replace: true });
    }
  }

  useEffect(() => {
    if (!sessionId) return;
    api
      .get<SessionRead>(`/sessions/${sessionId}`)
      .then((s) => {
        setStartedAt(new Date(s.started_at).getTime());
        setTargetMinutes(s.target_minutes);
      })
      .catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, draftQuestion]);

  useEffect(() => {
    if (status !== "ended" || !sessionId || closing || terminating) return;
    setClosing(true);
    api
      .post(`/sessions/${sessionId}/close`)
      .finally(() => navigate(`/sessions/${sessionId}`, { replace: true }));
  }, [status, sessionId, closing, navigate]);

  const elapsed = useElapsedTimer(startedAt, status !== "ended" && status !== "error");

  return (
    <Layout showFooter={false}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 rounded-full border border-white/12 bg-white/5 px-3 py-1.5 text-sm text-white/70">
          <Clock size={14} />
          {elapsed}
          {targetMinutes && (
            <span className="text-white/40">/ ~{targetMinutes}m target</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <LiveMediaControls />
          {status !== "ended" && status !== "error" && (
            <Button variant="danger" onClick={handleTerminate} disabled={terminating}>
              {terminating ? "Ending…" : "Terminate"}
            </Button>
          )}
        </div>
      </div>

      <GlassCard className="mt-4 flex h-[62vh] flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {turns.map((t, i) => (
            <div key={i} className="space-y-3">
              <ChatBubble role="interviewer" text={t.question} />
              {t.answer && <ChatBubble role="candidate" text={t.answer} />}
            </div>
          ))}
          {draftQuestion && <ChatBubble role="interviewer" text={draftQuestion} />}
          {status === "connecting" && <p className="text-sm text-white/40">Connecting…</p>}
          {status === "waiting_for_next_question" && (
            <p className="text-sm text-white/40">Interviewer is thinking…</p>
          )}
          {status === "ended" && (
            <p className="text-sm text-white/50">
              {endMessage ?? "Interview complete."} Generating your report…
            </p>
          )}
          {status === "error" && (
            <p className="text-sm text-[color:var(--color-bad)]">{errorMessage}</p>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="mt-4 border-t border-white/10 pt-4">
          <ChatComposer disabled={status !== "awaiting_answer" || terminating} onSend={sendAnswer} />
        </div>
      </GlassCard>
    </Layout>
  );
}
