"use client";

import { motion, type HTMLMotionProps } from "motion/react";

type Variant = "primary" | "soft" | "ghost";

const styles: Record<Variant, string> = {
  primary: "bg-accent text-white shadow-sm shadow-accent/15 hover:bg-accent/90",
  soft: "border border-line bg-white text-ink hover:border-accent/30 hover:bg-purple-soft/50",
  ghost: "text-muted hover:bg-purple-soft/60 hover:text-purple",
};

export function Button({ variant = "primary", className = "", ...props }: HTMLMotionProps<"button"> & { variant?: Variant }) {
  return (
    <motion.button
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 28 }}
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl px-5 py-2.5 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  );
}
