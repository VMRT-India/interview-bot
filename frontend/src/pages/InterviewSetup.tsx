import { FileText, Upload } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { ModelKeyPicker } from "../components/interview/ModelKeyPicker";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { api, ApiError } from "../lib/apiClient";
import type { InterviewType, SessionRead } from "../lib/types";

const TYPES: { id: InterviewType; label: string; body: string }[] = [
  { id: "TECHNICAL", label: "Technical", body: "DSA, system design, language/framework depth." },
  { id: "BEHAVIORAL", label: "Behavioral", body: "STAR-format, conflict, leadership scenarios." },
  { id: "HR", label: "HR", body: "Culture fit, motivation, communication." },
];

type JdMode = "paste" | "upload";

function PdfDropzone({
  label,
  file,
  onChange,
}: {
  label: string;
  file: File | null;
  onChange: (f: File | null) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-2xl border border-dashed border-white/20 bg-white/3 px-4 py-3 text-sm text-white/60 hover:border-[color:var(--color-accent)] hover:text-white">
      {file ? <FileText size={18} /> : <Upload size={18} />}
      <span className="flex-1 truncate">{file ? file.name : label}</span>
      <input
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}

export default function InterviewSetup() {
  const navigate = useNavigate();
  const [type, setType] = useState<InterviewType>("TECHNICAL");
  const [jdMode, setJdMode] = useState<JdMode>("paste");
  const [jdText, setJdText] = useState("");
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [llmProvider, setLlmProvider] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function start() {
    setSubmitting(true);
    setError(null);
    setQuotaExceeded(false);
    try {
      const session = await api.post<SessionRead>("/sessions", {
        interview_type: type,
        jd_text: jdMode === "paste" ? jdText.trim() || null : null,
        llm_provider: llmProvider ?? null,
      });

      if (jdMode === "upload" && jdFile) {
        await api.upload(`/sessions/${session.id}/upload-jd`, jdFile);
      }
      if (resumeFile) {
        await api.upload(`/sessions/${session.id}/upload-resume`, resumeFile);
      }

      navigate(`/interview/${session.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setQuotaExceeded(true);
        setError(err.message);
      } else {
        setError(err instanceof ApiError ? err.message : "Could not start the interview");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout showFooter={false}>
      <h1 className="text-2xl font-semibold text-white">Start a new interview</h1>

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        {TYPES.map((t) => (
          <button key={t.id} onClick={() => setType(t.id)} className="text-left">
            <GlassCard
              hover
              className={type === t.id ? "border border-[color:var(--color-accent)]" : ""}
            >
              <div className="font-medium text-white">{t.label}</div>
              <p className="mt-1 text-xs text-white/50">{t.body}</p>
            </GlassCard>
          </button>
        ))}
      </div>

      <div className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <label className="block text-sm text-white/60">
            Job description (optional) — makes questions role-specific and researches a realistic
            interview length
          </label>
          <div className="flex gap-1 rounded-full border border-white/12 bg-white/5 p-0.5 text-xs">
            {(["paste", "upload"] as JdMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setJdMode(m)}
                className={`rounded-full px-3 py-1 capitalize transition-colors ${
                  jdMode === m ? "bg-[color:var(--color-accent)] text-white" : "text-white/50"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {jdMode === "paste" ? (
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            rows={5}
            placeholder="Paste a job description to tailor the interview…"
            className="w-full resize-none rounded-2xl border border-white/15 bg-white/5 px-4 py-3 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)]"
          />
        ) : (
          <PdfDropzone label="Upload job description (PDF)" file={jdFile} onChange={setJdFile} />
        )}
      </div>

      <div className="mt-4">
        <label className="mb-2 block text-sm text-white/60">
          Resume (optional) — lets the interviewer ask about your actual projects
        </label>
        <PdfDropzone label="Upload resume (PDF)" file={resumeFile} onChange={setResumeFile} />
      </div>

      <div className="mt-6">
        <ModelKeyPicker provider={llmProvider} onChange={setLlmProvider} />
      </div>

      {error && (
        <p className="mt-4 text-sm text-[color:var(--color-bad)]">
          {error}
          {quotaExceeded && (
            <>
              {" "}
              <Link to="/settings" className="text-[color:var(--color-accent-soft)] underline">
                Add your own API key in Settings
              </Link>
              .
            </>
          )}
        </p>
      )}

      <div className="mt-6">
        <Button onClick={start} disabled={submitting}>
          {submitting ? "Starting…" : "Start interview"}
        </Button>
      </div>
    </Layout>
  );
}
