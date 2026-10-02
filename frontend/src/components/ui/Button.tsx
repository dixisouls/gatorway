"use client";

import { motion, type HTMLMotionProps } from "motion/react";

type Variant = "primary" | "soft" | "ghost";

const styles: Record<Variant, string> = {
  primary: "bg-purple text-white shadow-soft hover:bg-[#2d1a7a]",
  soft: "bg-purple-soft text-purple hover:bg-[#e2dcf5]",
  ghost: "text-muted hover:bg-purple-soft/60 hover:text-purple",
};

export function Button({ variant = "primary", className = "", ...props }: HTMLMotionProps<"button"> & { variant?: Variant }) {
  return (
    <motion.button
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 28 }}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  );
}
