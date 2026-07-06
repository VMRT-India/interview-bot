import { useEffect, useState } from "react";
import { Layout } from "../components/layout/Layout";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { useAuth } from "../context/AuthContext";
import { api, ApiError } from "../lib/apiClient";
import type { UserAPIKeyRead } from "../lib/types";

function Field({
  placeholder,
  value,
  onChange,
  type = "text",
}: {
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)]"
    />
  );
}

function IdentifierLinking() {
  const { user, refreshUser } = useAuth();
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function linkEmail() {
    try {
      await api.put("/auth/me/link-email", { email });
      await refreshUser();
      setMessage("Email linked.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to link email");
    }
  }

  async function linkPhone() {
    try {
      await api.put("/auth/me/link-phone", { phone_number: phone });
      await refreshUser();
      setMessage("Phone linked.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to link phone");
    }
  }

  return (
    <GlassCard>
      <h2 className="font-medium text-white">Account identifiers</h2>
      <div className="mt-3 flex flex-col gap-2 text-sm text-white/60">
        <div>Email: {user?.email ?? <span className="text-white/35">not linked</span>}</div>
        <div>Phone: {user?.phone_number ?? <span className="text-white/35">not linked</span>}</div>
      </div>

      {!user?.email && (
        <div className="mt-4 flex gap-2">
          <Field placeholder="Add an email" value={email} onChange={setEmail} type="email" />
          <Button variant="ghost" onClick={linkEmail} disabled={!email}>
            Link
          </Button>
        </div>
      )}
      {!user?.phone_number && (
        <div className="mt-2 flex gap-2">
          <Field placeholder="Add a phone number" value={phone} onChange={setPhone} type="tel" />
          <Button variant="ghost" onClick={linkPhone} disabled={!phone}>
            Link
          </Button>
        </div>
      )}
      {message && <p className="mt-2 text-xs text-white/50">{message}</p>}
    </GlassCard>
  );
}

function PasswordManagement() {
  const { user, refreshUser } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function setOrChange() {
    setMessage(null);
    try {
      if (user?.has_password) {
        await api.put("/auth/me/change-password", {
          current_password: current,
          new_password: next,
        });
      } else {
        await api.put("/auth/me/set-password", { password: next });
      }
      await refreshUser();
      setCurrent("");
      setNext("");
      setMessage("Password updated.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to update password");
    }
  }

  async function resetViaOAuth() {
    setMessage(null);
    try {
      await api.put("/auth/me/reset-password", { password: next });
      await refreshUser();
      setNext("");
      setMessage("Password reset using your current sign-in.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to reset password");
    }
  }

  return (
    <GlassCard>
      <h2 className="font-medium text-white">Password</h2>
      <div className="mt-3 flex flex-col gap-2">
        {user?.has_password && (
          <Field
            placeholder="Current password"
            value={current}
            onChange={setCurrent}
            type="password"
          />
        )}
        <Field placeholder="New password" value={next} onChange={setNext} type="password" />
        <div className="flex gap-2">
          <Button
            variant="ghost"
            onClick={setOrChange}
            disabled={!next || (user?.has_password && !current)}
          >
            {user?.has_password ? "Change password" : "Set password"}
          </Button>
          {user?.has_password && (
            <Button variant="ghost" onClick={resetViaOAuth} disabled={!next}>
              Reset via current sign-in
            </Button>
          )}
        </div>
        <p className="text-[11px] text-white/35">
          "Reset via current sign-in" only makes sense right after logging in with Google/GitHub
          — it skips the current-password check.
        </p>
        {message && <p className="text-xs text-white/50">{message}</p>}
      </div>
    </GlassCard>
  );
}

function ApiKeyManagement() {
  const [keys, setKeys] = useState<UserAPIKeyRead[]>([]);
  const [provider, setProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  function load() {
    api.get<UserAPIKeyRead[]>("/auth/me/api-keys").then(setKeys).catch(() => {});
  }
  useEffect(load, []);

  async function save() {
    try {
      await api.put("/auth/me/api-keys", {
        provider,
        api_key: apiKey,
        base_url: baseUrl || null,
      });
      setProvider("");
      setApiKey("");
      setBaseUrl("");
      setMessage("Key saved.");
      load();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to save key");
    }
  }

  async function remove(p: string) {
    await api.del(`/auth/me/api-keys/${p}`);
    load();
  }

  return (
    <GlassCard>
      <h2 className="font-medium text-white">Your API keys (BYOK)</h2>
      <p className="mt-1 text-xs text-white/45">
        Stored encrypted at rest, never shown again after saving.
      </p>

      <div className="mt-3 flex flex-col gap-2">
        {keys.map((k) => (
          <div
            key={k.id}
            className="flex items-center justify-between rounded-xl border border-white/10 bg-white/3 px-3 py-2 text-sm"
          >
            <span className="text-white/75">{k.provider}</span>
            <Button variant="danger" onClick={() => remove(k.provider)}>
              Remove
            </Button>
          </div>
        ))}
        {keys.length === 0 && <p className="text-xs text-white/40">No keys stored yet.</p>}
      </div>

      <div className="mt-4 flex flex-col gap-2 border-t border-white/10 pt-4">
        <Field placeholder="Provider (groq, gemini, openai, custom…)" value={provider} onChange={setProvider} />
        <Field placeholder="API key" value={apiKey} onChange={setApiKey} type="password" />
        <Field placeholder="Base URL (only for custom providers)" value={baseUrl} onChange={setBaseUrl} />
        <Button variant="ghost" onClick={save} disabled={!provider || !apiKey}>
          Save key
        </Button>
        {message && <p className="text-xs text-white/50">{message}</p>}
      </div>
    </GlassCard>
  );
}

export default function Settings() {
  return (
    <Layout showFooter={false}>
      <h1 className="text-2xl font-semibold text-white">Settings</h1>
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <IdentifierLinking />
        <PasswordManagement />
        <div className="lg:col-span-2">
          <ApiKeyManagement />
        </div>
      </div>
    </Layout>
  );
}
