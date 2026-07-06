import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { GlassCard } from "../components/ui/GlassCard";
import { useAuth } from "../context/AuthContext";
import { api, ApiError } from "../lib/apiClient";
import type { TokenResponse } from "../lib/types";

/**
 * Lands here after Google/GitHub redirect the browser back with ?code&state.
 * `OAUTH_REDIRECT_BASE_URL` on the backend must be set to this frontend's origin
 * (and the same URL registered in the provider's console) so the provider redirects
 * here instead of straight to the API — the backend callback route itself is
 * unchanged and is simply called from here via fetch.
 */
export default function OAuthCallback() {
  const { provider } = useParams<{ provider: string }>();
  const [params] = useSearchParams();
  const { loginWithToken } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state");
    if (!code || !state || !provider) {
      setError("Missing OAuth code/state — please try logging in again.");
      return;
    }

    api
      .get<TokenResponse>(
        `/auth/${provider}/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
        false
      )
      .then(async (res) => {
        await loginWithToken(res.access_token);
        navigate("/dashboard", { replace: true });
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "OAuth sign-in failed");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider]);

  return (
    <Layout showFooter={false}>
      <div className="mx-auto max-w-md pt-16">
        <GlassCard className="text-center">
          {error ? (
            <>
              <p className="text-[color:var(--color-bad)]">{error}</p>
              <button
                onClick={() => navigate("/login")}
                className="mt-4 text-sm text-[color:var(--color-accent-soft)]"
              >
                Back to login
              </button>
            </>
          ) : (
            <p className="text-white/60">Signing you in…</p>
          )}
        </GlassCard>
      </div>
    </Layout>
  );
}
