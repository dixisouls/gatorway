"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtUnits, kindLabel, slotCodes } from "@/lib/format";
import { geLabel, isGeSlot } from "@/lib/ge";
import type { AppliedEdit, CourseDetail, Slot } from "@/lib/types";
import { Button } from "./ui/Button";
import { Sparkle } from "./ui/Sparkle";
import { Sheet } from "./ui/Sheet";

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
  const yourChoice = applied?.reason === "Your choice";
  const requirement = geRow && slot.codes.length > 0 ? geLabel(slot).split(":")[0] : null; // which GE area this course fills
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
    ? "border-purple/40 bg-purple-soft/40 ring-1 ring-purple/20"
    : isPick
    ? "border-gold bg-gradient-to-br from-gold-soft via-[#f6ecd0] to-[#fffaf0] ring-2 ring-gold/40 shadow-[0_10px_30px_-12px_rgba(178,157,108,0.75)]"
    : passed
      ? "border-[#d8e6dd] bg-[#f1f7f3]"
      : open
        ? "border-dashed border-purple/25 bg-white/50"
        : "border-line bg-white/90";

  return (
    <motion.article
      aria-busy={generating}
      initial={{ opacity: 0, y: 14, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: enterDelay, type: "spring", stiffness: 220, damping: 26 }}
      className={`course-card relative overflow-hidden border transition-colors hover:border-ink/30 ${tone}`}
    >
      {generating && <span aria-hidden="true" className="pointer-events-none absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-white/80 to-transparent bg-[length:200%_100%]" />}
      <button
        type="button"
        disabled={!clickable}
        aria-expanded={open ? undefined : expanded}
        aria-haspopup={clickable ? "dialog" : undefined}
        onMouseEnter={() => setWanted(true)}
        onFocus={() => setWanted(true)}
        onClick={() => (open ? onOpen() : setExpanded((v) => !v))}
        className="group flex w-full flex-col p-3.5 text-left disabled:cursor-default"
      >
        <span className="flex w-full items-start justify-between gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted">{open ? (kind ?? "Open slot") : slotCodes(slot)}</span>
          {slot.units > 0 && <span className="shrink-0 rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-muted ring-1 ring-line">{fmtUnits(slot.units)} units</span>}
        </span>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={`${codesKey}|${slot.title}`}
            className="mt-2 line-clamp-2 text-sm font-medium leading-snug text-ink"
            initial={{ opacity: 0, filter: "blur(4px)" }}
            animate={{ opacity: 1, filter: "blur(0px)" }}
            exit={{ opacity: 0, filter: "blur(4px)" }}
            transition={{ duration: 0.3 }}
          >
            {slot.title}
          </motion.span>
        </AnimatePresence>
        <span className="mt-auto flex flex-wrap items-center gap-2 pt-2 text-xs">
          {passed && <span className="text-purple">✓ Completed</span>}
          {isPick && (
            <span className="inline-flex items-center gap-1 rounded-full bg-white/80 px-2 py-0.5 text-accent ring-1 ring-accent/20">
              <Sparkle size={12} /> {yourChoice ? "Your choice" : "Picked for you"}
            </span>
          )}
          {open && slot.swappable && <span className="text-muted opacity-60 transition-opacity group-hover:opacity-100">See options →</span>}
          {geRow && open && !slot.swappable && !passed && <span className="text-muted opacity-60 transition-opacity group-hover:opacity-100">See courses →</span>}
          {requirement && <span className="text-muted">{requirement}</span>}
          {!open && kind && !isPick && <span className="text-muted">{kind}</span>}
          {!open && <span className="ml-auto text-muted transition-transform group-hover:translate-x-0.5" aria-hidden="true">↗</span>}
        </span>
        {isPick && applied?.reason && !yourChoice && <span className="mt-2 line-clamp-1 block text-xs leading-relaxed text-muted">{applied.reason}</span>}
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

      <Sheet open={expanded} onClose={() => setExpanded(false)} label={`${slotCodes(slot)} details`}>
        <div className="mb-8 flex items-start justify-between gap-4 border-b border-line pb-6">
          <div>
            <p className="eyebrow">{slotCodes(slot)} · {fmtUnits(slot.units)} units</p>
            <h2 className="mt-3 text-2xl font-medium tracking-tight">{slot.title}</h2>
          </div>
          <button type="button" onClick={() => setExpanded(false)} aria-label="Close" className="rounded-full p-2 text-muted hover:bg-purple-soft">✕</button>
        </div>
        {details === null ? <p role="status" className="text-sm text-muted">Loading details…</p> : (
            <div className="space-y-6 text-sm">
              {Object.keys(details).length === 0 && <p className="text-muted">Course details aren&apos;t available right now.</p>}
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
              {isPick && applied?.reason && !yourChoice && (
                <p className="flex gap-2 rounded-xl bg-white/70 px-3 py-2 text-xs leading-relaxed text-muted">
                  <Sparkle size={13} className="mt-0.5 shrink-0" /> {applied.reason}
                </p>
              )}
              {slot.swappable && !passed && (
                <Button variant="soft" className="!px-4 !py-1.5 text-xs" onClick={() => { setExpanded(false); onOpen(); }}>
                  See other options
                </Button>
              )}
            </div>
        )}
      </Sheet>
    </motion.article>
  );
}
