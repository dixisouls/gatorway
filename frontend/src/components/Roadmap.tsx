"use client";

import { motion } from "motion/react";
import { useId, useState } from "react";
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

const between = (lo: number, hi: number) => lo + Math.random() * (hi - lo);

/** Every arrow gets its own random character: which way it leans, how it bends, how fast it draws, and how a small light travels along it. */
function randomArrow() {
  const flip = Math.random() < 0.5;
  const x0 = between(40, 130);
  const x1 = between(190, 280);
  const d = `M${x0.toFixed(0)} 6 C ${between(10, 300).toFixed(0)} ${between(30, 90).toFixed(0)}, ${between(10, 300).toFixed(0)} ${between(-10, 60).toFixed(0)}, ${x1.toFixed(0)} 84`;
  return {
    d, flip, x0, x1,
    draw: between(0.7, 1.6), // seconds to draw
    delay: between(0, 0.35),
    ease: ([[0.22, 1, 0.36, 1], [0.45, 0, 0.55, 1], [0.16, 1, 0.3, 1], "easeOut"] as const)[Math.floor(Math.random() * 4)],
    travel: between(2.4, 5.2), // seconds for the light to run the arrow
    travelDelay: between(0.8, 2.5),
    glow: between(5, 9),
  };
}

/** The curve under a semester, leading on to the next one: draws itself in when scrolled into view, then a small light keeps travelling along it. */
function TermArrow() {
  const id = useId();
  const [arrow] = useState(randomArrow); // chosen once per arrow, so each is different but none re-rolls while you read
  const view = { once: true, margin: "-40px" } as const;
  return (
    <div data-testid="term-arrow" aria-hidden="true" className="term-arrow">
      <svg viewBox="0 0 320 96" fill="none" className="h-20 w-full max-w-xs overflow-visible" style={arrow.flip ? { transform: "scaleX(-1)" } : undefined}>
        <defs>
          <linearGradient id={`${id}-g`} x1="0" y1="0" x2="320" y2="0" gradientUnits="userSpaceOnUse">
            <stop stopColor="#b29d6c" />
            <stop offset="1" stopColor="#4a35a8" />
          </linearGradient>
        </defs>
        <motion.path d={arrow.d} stroke={`url(#${id}-g)`} strokeOpacity="0.28" strokeWidth={arrow.glow} strokeLinecap="round" initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={view} transition={{ duration: arrow.draw, delay: arrow.delay, ease: arrow.ease }} />
        <motion.path d={arrow.d} stroke={`url(#${id}-g)`} strokeWidth="1.6" strokeLinecap="round" initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={view} transition={{ duration: arrow.draw, delay: arrow.delay, ease: arrow.ease }} />
        <motion.circle cx={arrow.x0} cy="6" r="3.5" fill="#b29d6c" initial={{ scale: 0 }} whileInView={{ scale: 1 }} viewport={view} transition={{ type: "spring", stiffness: 300, damping: 18, delay: arrow.delay }} />
        <motion.path d={`M${arrow.x1 - 7} 76 L${arrow.x1} 88 L${arrow.x1 + 7} 76`} stroke="#4a35a8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={view} transition={{ delay: arrow.delay + arrow.draw * 0.8, duration: 0.3 }} />
        <motion.circle
          r="2.6"
          fill="#4a35a8"
          style={{ offsetPath: `path("${arrow.d}")` }}
          initial={{ opacity: 0, offsetDistance: "0%" }}
          whileInView={{ opacity: [0, 1, 1, 0], offsetDistance: ["0%", "0%", "100%", "100%"] }}
          viewport={view}
          transition={{ duration: arrow.travel, delay: arrow.delay + arrow.draw + arrow.travelDelay, repeat: Infinity, ease: "easeInOut", times: [0, 0.08, 0.92, 1] }}
        />
      </svg>
    </div>
  );
}

export function Roadmap({ pathway, baselineSlots, applied, isRevealed, generating, onOpen, choices = {}, onChoose = () => {}, done, onToggleDone, creditAreas = [] }: RoadmapProps) {
  const terms = [...pathway.terms].sort((a, b) => a.position - b.position).filter((t) => t.slots.length > 0);
  const delays = revealDelays(terms);

  return (
    <div className="semester-board">
      {terms.map((term, index) => (
        <div key={term.position} className="term-cell">
        <section aria-label={term.label} className="term-section">
          <div className="term-heading">
            <div className="flex items-center gap-3"><span className="semester-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span><h3 className="text-ink">{term.label}</h3></div>
            <span className="text-xs text-muted">{fmtUnits(termUnits(term))} units</span>
          </div>
          <div className="grid items-start gap-2">
            {groupChoices(term.slots).map((item) => {
              if (item.kind === "choice") {
                const chosen = choices[item.header.slot_id] ?? item.options.find((o) => o.status === "passed")?.codes[0];
                return (
                  <div key={item.header.slot_id} className="rounded-sm border border-dashed border-ink/20 bg-white/20 p-3">
                    <div className="mb-1 flex items-baseline justify-between px-1">
                      <p className="text-xs font-medium uppercase tracking-wider text-muted">Choose one</p>
                      <span className="text-sm text-muted">{fmtUnits(item.header.units)} units</span>
                    </div>
                    <h4 className="mb-3 px-1 font-serif text-lg text-ink">{item.header.title.replace(/:\s*$/, "")}</h4>
                    <div className="grid items-start gap-2">
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
        {index < terms.length - 1 && <TermArrow />}
        </div>
      ))}
    </div>
  );
}
