"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtUnits, kindLabel, slotCodes } from "@/lib/format";
import { isGeSlot } from "@/lib/ge";
import type { AppliedEdit, CourseDetail, Slot } from "@/lib/types";
import { Button } from "./ui/Button";
import { Sparkle } from "./ui/Sparkle";

export interface CourseCardProps {
  slot: Slot;
  applied?: AppliedEdit;
  isPick: boolean; // an AI (or student) pick that has landed
  generating: boolean; // the AI is still deciding this slot
  enterDelay: number;
  onOpen: () => void; // opens the options sheet for this slot
  selectable?: { selected: boolean; onSelect: () => void }; // an option inside a "Choose one" group
  done?: boolean; // the student marked this GE requirement completed
  onToggleDone?: () => void; // shows the mark-as-completed control (GE rows)
  hint?: string; // e.g. "You have GE 4 credit on your transcript"
}

export function CourseCard({ slot, applied, isPick, generating, enterDelay, onOpen, selectable, done, onToggleDone, hint }: CourseCardProps) {
  const geRow = isGeSlot(slot);
  const passed = slot.status === "passed" || !!done;
  const open = slot.codes.length === 0;
  const clickable = !open || slot.swappable || geRow;
  const kind = kindLabel(slot);
  const codesKey = slot.codes.join("|");
  const [expanded, setExpanded] = useState(false);
  const [wanted, setWanted] = useState(false); // hovering or focusing starts the fetch, so the click can open it at once
  const [loaded, setLoaded] = useState<{ key: string; data: Record<string, CourseDetail> } | null>(null);
  const details = loaded?.key === codesKey ? loaded.data : null;

  useEffect(() => {
    if (!(expanded || wanted) || !codesKey || details !== null) return;
    let alive = true;
    api
      .courses(codesKey.split("|"))
      .then((r) => alive && setLoaded({ key: codesKey, data: r.courses }))
      .catch(() => alive && setLoaded({ key: codesKey, data: {} }));
    return () => {
      alive = false;
    };
  }, [expanded, wanted, codesKey, details]);

  const tone = selectable?.selected
    ? "border-purple/40 bg-gradient-to-br from-purple-soft/80 to-white ring-2 ring-purple/20"
    : isPick
    ? "border-gold/40 bg-gradient-to-br from-gold-soft/80 to-white"
    : passed
      ? "border-purple/10 bg-purple-soft/50"
      : open
        ? "border-dashed border-purple/25 bg-white/50"
        : "border-line bg-white/90";

  return (
    <motion.article
      aria-busy={generating}
      initial={{ opacity: 0, y: 14, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: enterDelay, type: "spring", stiffness: 220, damping: 26 }}
      className={`relative overflow-hidden rounded-[1.4rem] border shadow-soft ${tone}`}
    >
      {generating && <span aria-hidden="true" className="pointer-events-none absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-white/80 to-transparent bg-[length:200%_100%]" />}
      <button
        type="button"
        disabled={!clickable}
        aria-expanded={open ? undefined : expanded}
        onMouseEnter={() => setWanted(true)}
        onFocus={() => setWanted(true)}
        onClick={() => (open ? onOpen() : setExpanded((v) => !v))}
        className="group flex min-h-[7.5rem] w-full flex-col p-4 text-left disabled:cursor-default"
      >
        <span className="flex w-full items-start justify-between gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted">{open ? (kind ?? "Open slot") : slotCodes(slot)}</span>
          {slot.units > 0 && <span className="shrink-0 rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-muted ring-1 ring-line">{fmtUnits(slot.units)} units</span>}
        </span>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={`${codesKey}|${slot.title}`}
            className="mt-2 block font-serif text-[1.02rem] leading-snug text-ink"
            initial={{ opacity: 0, filter: "blur(4px)" }}
            animate={{ opacity: 1, filter: "blur(0px)" }}
            exit={{ opacity: 0, filter: "blur(4px)" }}
            transition={{ duration: 0.3 }}
          >
            {slot.title}
          </motion.span>
        </AnimatePresence>
        <span className="mt-auto flex flex-wrap items-center gap-2 pt-3 text-xs">
          {passed && <span className="text-purple">✓ Completed</span>}
          {isPick && (
            <span className="inline-flex items-center gap-1 rounded-full bg-white/80 px-2 py-0.5 text-[#7a6a3c] ring-1 ring-gold/40">
              <Sparkle size={12} /> Picked for you
            </span>
          )}
          {open && slot.swappable && <span className="text-muted opacity-60 transition-opacity group-hover:opacity-100">See options →</span>}
          {geRow && !passed && <span className="text-muted opacity-60 transition-opacity group-hover:opacity-100">See courses →</span>}
          {!open && expanded && details === null && <span className="text-muted">Loading details…</span>}
          {!open && !expanded && <span className="text-muted opacity-0 transition-opacity group-hover:opacity-100">Tap for details</span>}
          {!open && kind && !isPick && <span className="text-muted">{kind}</span>}
        </span>
        {isPick && applied?.reason && !expanded && <span className="mt-2 line-clamp-2 block text-xs leading-relaxed text-muted">{applied.reason}</span>}
      </button>

      {geRow && ((hint && !done) || onToggleDone) && (
        <div className="space-y-2 px-4 pb-3">
          {hint && !done && <p className="text-xs text-[#7a6a3c]">{hint}</p>}
          {onToggleDone && (
            <Button variant={done ? "ghost" : "soft"} className="!px-4 !py-1.5 text-xs" onClick={onToggleDone}>
              {done ? "Undo" : "Mark as completed"}
            </Button>
          )}
        </div>
      )}

      {selectable && (
        <div className="px-4 pb-3">
          {selectable.selected ? (
            <span className="inline-flex items-center rounded-full bg-purple px-3 py-1 text-xs text-white">✓ Your choice</span>
          ) : (
            <Button variant="soft" className="!px-4 !py-1.5 text-xs" onClick={selectable.onSelect}>
              Choose this
            </Button>
          )}
        </div>
      )}

      <AnimatePresence initial={false}>
        {expanded && details !== null && (
          <motion.div key="more" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ height: { duration: 0.32, ease: [0.22, 1, 0.36, 1] }, opacity: { duration: 0.2 } }} className="overflow-hidden">
            <div className="space-y-3 border-t border-line px-4 pb-4 pt-3 text-sm">
              {slot.codes.map((code) => {
                const d = details[code];
                if (!d) return null;
                return (
                  <div key={code} className="space-y-2">
                    {slot.codes.length > 1 && <p className="font-medium text-ink">{code} · {d.title}</p>}
                    {d.description && <p className="leading-relaxed text-ink/90">{d.description}</p>}
                    {d.prereq_text && (
                      <p className="text-muted">
                        <span className="font-medium text-ink/80">Prerequisites · </span>
                        {d.prereq_text}
                      </p>
                    )}
                    {d.attributes.length > 0 && (
                      <ul className="flex flex-wrap gap-1.5">
                        {d.attributes.map((a) => (
                          <li key={a} className="rounded-full bg-purple-soft/70 px-2.5 py-0.5 text-xs text-purple">
                            {a}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
              {isPick && applied?.reason && (
                <p className="flex gap-2 rounded-xl bg-white/70 px-3 py-2 text-xs leading-relaxed text-muted">
                  <Sparkle size={13} className="mt-0.5 shrink-0" /> {applied.reason}
                </p>
              )}
              {slot.swappable && !passed && (
                <Button variant="soft" className="!px-4 !py-1.5 text-xs" onClick={onOpen}>
                  See other options
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}
