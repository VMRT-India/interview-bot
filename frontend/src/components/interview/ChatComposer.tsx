import { Send } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { Button } from "../ui/Button";

export function ChatComposer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex items-end gap-3">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={2}
        placeholder={disabled ? "Waiting for the next question…" : "Type your answer…"}
        className="flex-1 resize-none rounded-2xl border border-white/15 bg-white/5 px-4 py-3 text-sm text-white placeholder:text-white/35 outline-none focus:border-[color:var(--color-accent)] disabled:opacity-40"
      />
      <Button onClick={submit} disabled={disabled || !value.trim()}>
        <Send size={16} />
      </Button>
    </div>
  );
}
