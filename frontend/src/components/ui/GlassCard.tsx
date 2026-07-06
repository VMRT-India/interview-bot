import { motion } from "framer-motion";
import type { ReactNode } from "react";

export function GlassCard({
  children,
  className = "",
  tight = false,
  hover = false,
}: {
  children: ReactNode;
  className?: string;
  tight?: boolean;
  hover?: boolean;
}) {
  const base = tight ? "glass-panel-tight" : "glass-panel";
  return (
    <motion.div
      className={`${base} p-6 ${className}`}
      whileHover={hover ? { y: -3, boxShadow: "0 12px 40px rgba(10,132,255,0.18)" } : undefined}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
    >
      {children}
    </motion.div>
  );
}
