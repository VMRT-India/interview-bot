import { motion } from "framer-motion";
import type { MouseEventHandler, ReactNode } from "react";

interface ButtonProps {
  children: ReactNode;
  variant?: "primary" | "ghost" | "danger";
  className?: string;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  onClick?: MouseEventHandler<HTMLButtonElement>;
}

const variants: Record<string, string> = {
  primary:
    "bg-[color:var(--color-accent)] text-white shadow-[0_4px_20px_rgba(10,132,255,0.4)] hover:brightness-110",
  ghost:
    "bg-white/8 text-white border border-white/15 hover:bg-white/14",
  danger: "bg-[color:var(--color-bad)]/90 text-white hover:brightness-110",
};

export function Button({
  children,
  variant = "primary",
  className = "",
  disabled,
  type = "button",
  onClick,
}: ButtonProps) {
  return (
    <motion.button
      type={type}
      onClick={onClick}
      whileTap={{ scale: disabled ? 1 : 0.97 }}
      whileHover={{ scale: disabled ? 1 : 1.02 }}
      disabled={disabled}
      className={`rounded-2xl px-5 py-2.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${variants[variant]} ${className}`}
    >
      {children}
    </motion.button>
  );
}
