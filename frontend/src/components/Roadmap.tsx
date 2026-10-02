"use client";

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

export function Roadmap({ pathway, baselineSlots, applied, isRevealed, generating, onOpen, choices = {}, onChoose = () => {}, done, onToggleDone, creditAreas = [] }: RoadmapProps) {
  const terms = [...pathway.terms].sort((a, b) => a.position - b.position).filter((t) => t.slots.length > 0);
  const delays = revealDelays(terms);

  return (
    <div className="semester-board">
      {terms.map((term, index) => (
        <section key={term.position} aria-label={term.label} className="term-section">
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
      ))}
    </div>
  );
}
