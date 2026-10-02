"use client";

import { motion } from "motion/react";
import { useId } from "react";
import { fmtUnits, termUnits } from "@/lib/format";
import { creditHint, isGeSlot } from "@/lib/ge";
import { groupChoices } from "@/lib/groups";
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
  choices?: Record<string, string>; // "Select One" row id -> the code the student chose
  onChoose?: (headerId: string, code: string) => void;
  done?: ReadonlySet<string>; // GE rows the student marked completed
  onToggleDone?: (slotId: string) => void;
  creditAreas?: string[]; // GE areas the transcript already has credit for
}

/** A soft S-curve that drifts from one term to the next, alternating sides; draws itself in when scrolled into view. */
function TermArrow({ index }: { index: number }) {
  const id = useId();
  const flip = index % 2 === 0;
  const view = { once: true, margin: "-40px" } as const;
  return (
    <div data-testid="term-arrow" aria-hidden="true" className="flex justify-center py-1">
      <svg viewBox="0 0 320 96" fill="none" className="h-24 w-full max-w-sm overflow-visible" style={flip ? undefined : { transform: "scaleX(-1)" }}>
        <defs>
          <linearGradient id={`${id}-g`} x1="0" y1="0" x2="320" y2="0" gradientUnits="userSpaceOnUse">
            <stop stopColor="#b29d6c" />
            <stop offset="1" stopColor="#4a35a8" />
          </linearGradient>
        </defs>
        <motion.path d="M30 6 C 30 66, 290 28, 290 84" stroke={`url(#${id}-g)`} strokeOpacity="0.28" strokeWidth="7" strokeLinecap="round" initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={view} transition={{ duration: 0.9, ease: "easeOut" }} />
        <motion.path d="M30 6 C 30 66, 290 28, 290 84" stroke={`url(#${id}-g)`} strokeWidth="1.6" strokeLinecap="round" initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={view} transition={{ duration: 0.9, ease: "easeOut" }} />
        <motion.circle cx="30" cy="6" r="3.5" fill="#b29d6c" initial={{ scale: 0 }} whileInView={{ scale: 1 }} viewport={view} transition={{ type: "spring", stiffness: 300, damping: 18 }} />
        <motion.path d="M283 77 L290 88 L297 77" stroke="#4a35a8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={view} transition={{ delay: 0.75, duration: 0.3 }} />
      </svg>
    </div>
  );
}

export function Roadmap({ pathway, baselineSlots, applied, isRevealed, generating, onOpen, choices = {}, onChoose = () => {}, done, onToggleDone, creditAreas = [] }: RoadmapProps) {
  const terms = [...pathway.terms].sort((a, b) => a.position - b.position).filter((t) => t.slots.length > 0);
  const delays = revealDelays(terms);

  return (
    <div>
      {terms.map((term, i) => (
        <section key={term.position} aria-label={term.label}>
          {i > 0 && <TermArrow index={i} />}
          <div className="mb-3 flex items-baseline justify-between px-1">
            <h3 className="font-serif text-xl text-purple">{term.label}</h3>
            <span className="text-sm text-muted">{fmtUnits(termUnits(term))} units</span>
          </div>
          <div className="grid items-start gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {groupChoices(term.slots).map((item) => {
              if (item.kind === "choice") {
                const chosen = choices[item.header.slot_id] ?? item.options.find((o) => o.status === "passed")?.codes[0];
                return (
                  <div key={item.header.slot_id} className="rounded-[1.6rem] border border-dashed border-purple/25 bg-white/40 p-4 sm:col-span-2 lg:col-span-3">
                    <div className="mb-1 flex items-baseline justify-between px-1">
                      <p className="text-xs font-medium uppercase tracking-wider text-muted">Choose one</p>
                      <span className="text-sm text-muted">{fmtUnits(item.header.units)} units</span>
                    </div>
                    <h4 className="mb-3 px-1 font-serif text-lg text-ink">{item.header.title.replace(/:\s*$/, "")}</h4>
                    <div className="grid items-start gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {item.options.map((o) => (
                        <CourseCard
                          key={o.slot_id}
                          slot={o}
                          isPick={false}
                          generating={false}
                          enterDelay={delays[item.header.slot_id] ?? 0}
                          onOpen={() => onOpen(o)}
                          selectable={{ selected: chosen === o.codes[0], onSelect: () => onChoose(item.header.slot_id, o.codes[0]) }}
                        />
                      ))}
                    </div>
                  </div>
                );
              }
              const slot = item.slot;
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
                  done={done?.has(slot.slot_id)}
                  onToggleDone={onToggleDone && isGeSlot(slot) ? () => onToggleDone(slot.slot_id) : undefined}
                  hint={creditHint(slot, creditAreas)}
                />
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
