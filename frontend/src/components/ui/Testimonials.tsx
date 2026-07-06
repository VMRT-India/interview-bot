import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { GlassCard } from "./GlassCard";

const QUOTES = [
  {
    quote:
      "The follow-up questions genuinely adapted to what I said — it felt like a real technical screen, not a script.",
    name: "Priya S.",
    role: "Backend Engineer, practicing for a systems-design loop",
  },
  {
    quote:
      "I used the JD-aware mode against a real job posting and it asked things I hadn't even thought to prepare for.",
    name: "Marcus O.",
    role: "New-grad candidate",
  },
  {
    quote:
      "The turn-by-turn feedback on communication clarity, not just correctness, is what actually moved my score up.",
    name: "Aditi R.",
    role: "Data Scientist",
  },
];

export function Testimonials() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % QUOTES.length), 6000);
    return () => clearInterval(id);
  }, []);

  const current = QUOTES[index];

  return (
    <div className="mx-auto max-w-2xl">
      <AnimatePresence mode="wait">
        <motion.div
          key={index}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.4 }}
        >
          <GlassCard className="text-center">
            <p className="text-lg leading-relaxed text-white/90">“{current.quote}”</p>
            <div className="mt-4 text-sm text-white/55">
              <span className="font-medium text-white/80">{current.name}</span> · {current.role}
            </div>
          </GlassCard>
        </motion.div>
      </AnimatePresence>
      <div className="mt-4 flex justify-center gap-2">
        {QUOTES.map((_, i) => (
          <button
            key={i}
            aria-label={`Show testimonial ${i + 1}`}
            onClick={() => setIndex(i)}
            className={`h-1.5 w-6 rounded-full transition-colors ${
              i === index ? "bg-[color:var(--color-accent)]" : "bg-white/20"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
