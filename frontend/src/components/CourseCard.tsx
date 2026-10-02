"use client";

import { AnimatePresence, motion } from "motion/react";
import { fmtUnits, kindLabel, slotCodes } from "@/lib/format";
import type { AppliedEdit, Slot } from "@/lib/types";
import { Sparkle } from "./ui/Sparkle";

export interface CourseCardProps {
  slot: Slot;
  applied?: AppliedEdit;
  isPick: boolean; // an AI (or student) pick that has landed
  generating: boolean; // the AI is still deciding this slot
  enterDelay: number;
  onOpen: () => void;
}

export function CourseCard({ slot, applied, isPick, generating, enterDelay, onOpen }: CourseCardProps) {
  const passed = slot.status === "passed";
  const open = slot.codes.length === 0;
  const clickable = !open || slot.swappable;
  const kind = kindLabel(slot);
  const tone = isPick
    ? "border-gold/40 bg-gradient-to-br from-gold-soft/80 to-white"
    : passed
      ? "border-purple/10 bg-purple-soft/50"
      : open
        ? "border-dashed border-purple/25 bg-white/50"
        : "border-line bg-white/80";

  return (
    <motion.button
      type="button"
      disabled={!clickable}
      onClick={onOpen}
      aria-busy={generating}
      initial={{ opacity: 0, y: 14, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: enterDelay, type: "spring", stiffness: 220, damping: 26 }}
      whileHover={clickable ? { y: -3 } : undefined}
      whileTap={clickable ? { scale: 0.985 } : undefined}
      className={`group relative flex min-h-[7.5rem] flex-col overflow-hidden rounded-[1.4rem] border p-4 text-left shadow-soft backdrop-blur disabled:cursor-default ${tone}`}
    >
      {generating && (
        <span aria-hidden="true" className="pointer-events-none absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-white/80 to-transparent bg-[length:200%_100%]" />
      )}
      <div className="flex items-start justify-between gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted">{open ? (kind ?? "Open slot") : slotCodes(slot)}</span>
        <span className="shrink-0 rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-muted ring-1 ring-line">{fmtUnits(slot.units)} units</span>
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.p
          key={`${slot.codes.join("|")}|${slot.title}`}
          className="mt-2 font-serif text-[1.02rem] leading-snug text-ink"
          initial={{ opacity: 0, filter: "blur(4px)" }}
          animate={{ opacity: 1, filter: "blur(0px)" }}
          exit={{ opacity: 0, filter: "blur(4px)" }}
          transition={{ duration: 0.3 }}
        >
          {slot.title}
        </motion.p>
      </AnimatePresence>
      <div className="mt-auto flex flex-wrap items-center gap-2 pt-3 text-xs">
        {passed && <span className="text-purple">✓ Completed</span>}
        {isPick && (
          <span className="inline-flex items-center gap-1 rounded-full bg-white/80 px-2 py-0.5 text-[#7a6a3c] ring-1 ring-gold/40">
            <Sparkle size={12} /> Picked for you
          </span>
        )}
        {!passed && !isPick && slot.swappable && <span className="text-muted opacity-60 transition-opacity group-hover:opacity-100">See options →</span>}
        {!open && kind && !isPick && <span className="text-muted">{kind}</span>}
      </div>
      {isPick && applied?.reason && <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted">{applied.reason}</p>}
    </motion.button>
  );
}
