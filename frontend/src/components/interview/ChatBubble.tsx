import { motion } from "framer-motion";

export function ChatBubble({ role, text }: { role: "interviewer" | "candidate"; text: string }) {
  const isInterviewer = role === "interviewer";
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isInterviewer ? "justify-start" : "justify-end"}`}
    >
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isInterviewer
            ? "glass-panel-tight text-white/85"
            : "bg-[color:var(--color-accent)] text-white"
        }`}
      >
        {text}
      </div>
    </motion.div>
  );
}
