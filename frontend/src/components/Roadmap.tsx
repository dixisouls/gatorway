"use client";

import { motion } from "motion/react";
import { fmtUnits, termUnits } from "@/lib/format";
import { revealDelays } from "@/lib/reveal";
import type { AppliedEdit, Pathway, Slot } from "@/lib/types";
import { CourseCard } from "./CourseCard";

interface RoadmapProps {
  pathway: Pathway;
  baselineSlots: Record<string, Slot>; // what each slot looked like before any pick
  applied: Map<string, AppliedEdit>;
  isRevealed: (slotId: string) => boolean; // has the pick for this slot landed yet?
  generating: boolean; // the AI is still working
  onOpen: (slot: Slot) => void;
}

function TermArrow() {
  return (
    <div data-testid="term-arrow" aria-hidden="true" className="flex justify-center py-3">
      <svg width="24" height="56" viewBox="0 0 24 56" fill="none">
        <motion.path
          d="M12 2 C 12 18, 12 26, 12 46"
          stroke="#b29d6c"
          strokeWidth="1.6"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />
        <motion.path
          d="M6 40 L12 48 L18 40"
          stroke="#b29d6c"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ delay: 0.55, duration: 0.3 }}
        />
      </svg>
    </div>
  );
}

export function Roadmap({ pathway, baselineSlots, applied, isRevealed, generating, onOpen }: RoadmapProps) {
  const terms = [...pathway.terms].sort((a, b) => a.position - b.position).filter((t) => t.slots.length > 0);
  const delays = revealDelays(terms);

  return (
    <div>
      {terms.map((term, i) => (
        <section key={term.position} aria-label={term.label}>
          {i > 0 && <TermArrow />}
          <div className="mb-3 flex items-baseline justify-between px-1">
            <h3 className="font-serif text-xl text-purple">{term.label}</h3>
            <span className="text-sm text-muted">{fmtUnits(termUnits(term))} units</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {term.slots.map((slot) => {
              const revealed = isRevealed(slot.slot_id);
              const shown = slot.status === "replaced" && !revealed ? (baselineSlots[slot.slot_id] ?? slot) : slot;
              return (
                <CourseCard
                  key={slot.slot_id}
                  slot={shown}
                  applied={applied.get(slot.slot_id)}
                  isPick={slot.status === "replaced" && revealed}
                  generating={generating && shown.swappable && shown.status === "planned"}
                  enterDelay={delays[slot.slot_id] ?? 0}
                  onOpen={() => onOpen(slot)}
                />
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
