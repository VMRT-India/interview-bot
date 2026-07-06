import { useEffect, useState } from "react";
import { GlassCard } from "../ui/GlassCard";
import { Button } from "../ui/Button";
import { api, ApiError } from "../../lib/apiClient";
import type { UserAPIKeyRead } from "../../lib/types";

const PROVIDERS = [
  {
    id: "",
    label: "App default (demo key)",
    guide: "Uses the app's shared demo key — no setup needed, best for a quick try.",
  },
  {
    id: "groq",
    label: "Groq",
    guide: "Free key at console.groq.com/keys",
  },
  {
    id: "gemini",
    label: "Google Gemini",
    guide: "Free key at aistudio.google.com/apikey",
  },
  {
    id: "openai",
    label: "OpenAI",
    guide: "Key at platform.openai.com/api-keys (billed usage)",
  },
  {
    id: "custom",
    label: "Custom (OpenAI-compatible)",
    guide: "Any OpenAI-compatible endpoint — requires a base URL.",
  },
];

export function ModelKeyPicker({
  provider,
  onChange,
}: {
  provider: string | undefined;
  onChange: (provider: string | undefined) => void;
}) {
  const [savedKeys, setSavedKeys] = useState<UserAPIKeyRead[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api.get<UserAPIKeyRead[]>("/auth/me/api-keys").then(setSavedKeys).catch(() => {});
  }, []);

  const selected = PROVIDERS.find((p) => p.id === (provider ?? "")) ?? PROVIDERS[0];
  const hasSavedKey = savedKeys.some((k) => k.provider === selected.id);
  const needsKeyForm = selected.id !== "" && !hasSavedKey;

  async function saveKey() {
    setSaving(true);
    setMessage(null);
    try {
      const saved = await api.put<UserAPIKeyRead>("/auth/me/api-keys", {
        provider: selected.id,
        api_key: apiKey,
        base_url: selected.id === "custom" ? baseUrl : null,
      });
      setSavedKeys((prev) => [...prev.filter((k) => k.provider !== saved.provider), saved]);
      setApiKey("");
      setMessage("Key saved and encrypted.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to save key");
    } finally {
      setSaving(false);
    }
  }

  return (
    <GlassCard tight>
      <h3 className="text-sm font-medium text-white">Model & API key</h3>
      <p className="mt-1 text-xs text-white/45">
        Bring your own key to use your own quota, or stick with the app default.
      </p>

      <div className="mt-3 grid gap-2">
        {PROVIDERS.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => onChange(p.id || undefined)}
            className={`rounded-xl border px-3 py-2 text-left text-sm transition-colors ${
              selected.id === p.id
                ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent)]/10 text-white"
                : "border-white/10 bg-white/3 text-white/70 hover:bg-white/6"
            }`}
          >
            <div className="flex items-center justify-between">
              <span>{p.label}</span>
              {p.id !== "" && savedKeys.some((k) => k.provider === p.id) && (
                <span className="text-[10px] text-[color:var(--color-good)]">key saved</span>
              )}
            </div>
            <div className="mt-0.5 text-[11px] text-white/40">{p.guide}</div>
          </button>
        ))}
      </div>

      {needsKeyForm && (
        <div className="mt-4 flex flex-col gap-2 border-t border-white/10 pt-4">
          <input
            type="password"
            placeholder={`${selected.label} API key`}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)]"
          />
          {selected.id === "custom" && (
            <input
              type="text"
              placeholder="Base URL (e.g. https://api.example.com/v1)"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)]"
            />
          )}
          <Button
            type="button"
            variant="ghost"
            disabled={saving || !apiKey || (selected.id === "custom" && !baseUrl)}
            onClick={saveKey}
          >
            {saving ? "Saving…" : "Save key"}
          </Button>
          {message && <p className="text-xs text-white/50">{message}</p>}
        </div>
      )}
    </GlassCard>
  );
}
