import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { useAuth } from "../context/AuthContext";
import { API_BASE_URL, ApiError } from "../lib/apiClient";

export default function Login() {
  const { login, continueAsGuest } = useAuth();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(identifier, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGuest() {
    setError(null);
    setGuestLoading(true);
    try {
      await continueAsGuest();
      navigate("/interview/new");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start a guest trial");
    } finally {
      setGuestLoading(false);
    }
  }

  return (
    <Layout showFooter={false}>
      <div className="mx-auto max-w-md pt-8">
        <GlassCard>
          <h1 className="text-2xl font-semibold text-white">Welcome back</h1>
          <p className="mt-1 text-sm text-white/55">Log in to continue your interview practice.</p>

          <div className="mt-6 flex flex-col gap-3">
            <a href={`${API_BASE_URL}/auth/google/login`}>
              <Button variant="ghost" className="w-full" type="button">
                Continue with Google
              </Button>
            </a>
            <a href={`${API_BASE_URL}/auth/github/login`}>
              <Button variant="ghost" className="w-full" type="button">
                Continue with GitHub
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
              type="text"
              placeholder="Email or phone number"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              required
              className="rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)]"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)]"
            />
            {error && <p className="text-sm text-[color:var(--color-bad)]">{error}</p>}
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Logging in…" : "Log in"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-white/50">
            No account?{" "}
            <Link to="/signup" className="text-[color:var(--color-accent-soft)]">
              Sign up
            </Link>
          </p>

          <div className="my-6 flex items-center gap-3 text-xs text-white/35">
            <div className="h-px flex-1 bg-white/10" />
            or
            <div className="h-px flex-1 bg-white/10" />
          </div>

          <Button
            variant="ghost"
            className="w-full"
            type="button"
            disabled={guestLoading}
            onClick={handleGuest}
          >
            {guestLoading ? "Starting…" : "Try one interview without signing up"}
          </Button>
        </GlassCard>
      </div>
    </Layout>
  );
}
