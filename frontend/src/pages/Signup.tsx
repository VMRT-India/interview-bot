import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { useAuth } from "../context/AuthContext";
import { API_BASE_URL, ApiError } from "../lib/apiClient";

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signup(email, phone, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout showFooter={false}>
      <div className="mx-auto max-w-md pt-8">
        <GlassCard>
          <h1 className="text-2xl font-semibold text-white">Create your account</h1>
          <p className="mt-1 text-sm text-white/55">
            Email and phone are both required — it keeps one interviewer per candidate.
          </p>

          <div className="mt-6 flex flex-col gap-3">
            <a href={`${API_BASE_URL}/auth/google/login`}>
              <Button variant="ghost" className="w-full" type="button">
                Sign up with Google
              </Button>
            </a>
            <a href={`${API_BASE_URL}/auth/github/login`}>
              <Button variant="ghost" className="w-full" type="button">
                Sign up with GitHub
              </Button>
            </a>
          </div>

          <div className="my-6 flex items-center gap-3 text-xs text-white/35">
            <div className="h-px flex-1 bg-white/10" />
            or
            <div className="h-px flex-1 bg-white/10" />
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)]"
            />
            <input
              type="tel"
              placeholder="Phone number"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
              className="rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)]"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)]"
            />
            {error && <p className="text-sm text-[color:var(--color-bad)]">{error}</p>}
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Creating account…" : "Sign up"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-white/50">
            Already have an account?{" "}
            <Link to="/login" className="text-[color:var(--color-accent-soft)]">
              Log in
            </Link>
          </p>
        </GlassCard>
      </div>
    </Layout>
  );
}
