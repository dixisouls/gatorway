"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

export function useRotatingIndex(length: number, intervalMs: number): number {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIndex((n) => (n + 1) % length), intervalMs);
    return () => clearInterval(t);
  }, [length, intervalMs]);
  return index;
}

/** A calm, cross-fading list of phrases ("Reading each term…"), one at a time. */
export function RotatingWords({ phrases, intervalMs = 1900, compact = false }: { phrases: string[]; intervalMs?: number; compact?: boolean }) {
  const i = useRotatingIndex(phrases.length, intervalMs);
  return (
    <div className={compact ? "relative h-5 w-64 overflow-hidden text-left" : "relative h-8 overflow-hidden text-center"} aria-live="polite">
      <AnimatePresence mode="wait">
        <motion.span
          key={i}
          className={compact ? "absolute inset-x-0 text-sm text-ink" : "absolute inset-x-0 font-serif text-xl text-purple"}
          initial={{ opacity: 0, y: 10, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -10, filter: "blur(4px)" }}
          transition={{ duration: 0.45 }}
        >
          {phrases[i]}…
        </motion.span>
      </AnimatePresence>
    </div>
  );
}
