"use client";

import { motion } from "motion/react";
import { AuthCard } from "./AuthCard";
import { Aurora } from "./ui/Aurora";
import { Sparkle } from "./ui/Sparkle";

export function Landing() {
  return (
    <div className="relative min-h-dvh">
      <Aurora />
      <main className="mx-auto grid min-h-dvh max-w-5xl items-center gap-12 px-6 py-16 md:grid-cols-[1.2fr_1fr]">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: "easeOut" }}>
          <p className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs tracking-wide text-muted ring-1 ring-line">
            <Sparkle size={14} /> For San Francisco State students
          </p>
          <h1 className="mt-6 font-serif text-5xl leading-[1.05] text-purple sm:text-6xl">
            Your degree,
            <br />
            shaped around what you love.
          </h1>
          <p className="mt-6 max-w-md text-lg leading-relaxed text-muted">
            Upload your transcript, tell us what excites you, and watch a semester-by-semester roadmap take shape — electives chosen to fit you.
          </p>
        </motion.div>
        <motion.div className="justify-self-center md:justify-self-end" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.15, ease: "easeOut" }}>
          <AuthCard />
        </motion.div>
      </main>
    </div>
  );
}
