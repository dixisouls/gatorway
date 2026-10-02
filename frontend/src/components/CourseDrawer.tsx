"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { fmtUnits, kindLabel, slotCodes } from "@/lib/format";
import { geAreas, isGeSlot } from "@/lib/ge";
import type { AppliedEdit, Candidate, CourseDetail, SavedPathway, Slot } from "@/lib/types";
import { useDebounced } from "@/lib/useDebounced";
import { GeList } from "./GeList";
import { Button } from "./ui/Button";
import { Sheet } from "./ui/Sheet";
import { Sparkle } from "./ui/Sparkle";

export interface CourseDrawerProps {
  slot: Slot | null; // null = closed
  applied?: AppliedEdit;
  pathwayId: number | null;
  canSwap: boolean; // false while Gemini is still working
  onClose: () => void;
  onSwapped: (result: SavedPathway, slotId: string) => void;
  ge?: { done: boolean; onToggle: () => void; hint?: string }; // for a GE requirement row
}

export function CourseDrawer({ slot, applied, pathwayId, canSwap, onClose, onSwapped, ge }: CourseDrawerProps) {
  return (
    <Sheet open={slot !== null} onClose={onClose} label={slot ? `${slotCodes(slot) || slot.title} details` : "Course details"}>
      {slot && <DrawerBody key={slot.slot_id} slot={slot} applied={applied} pathwayId={pathwayId} canSwap={canSwap} onSwapped={onSwapped} onClose={onClose} ge={ge} />}
    </Sheet>
  );
}

function DrawerBody({ slot, applied, pathwayId, canSwap, onSwapped, onClose, ge }: Omit<CourseDrawerProps, "slot"> & { slot: Slot }) {
  const codesKey = slot.codes.join("|");
  const codes = useMemo(() => (codesKey ? codesKey.split("|") : []), [codesKey]);
  const [details, setDetails] = useState<Record<string, CourseDetail> | null>(null);
  const [query, setQuery] = useState("");
  const debounced = useDebounced(query.trim(), 300);
  const [loaded, setLoaded] = useState<{ q: string; items: Candidate[] } | null>(null);
  const [optionsError, setOptionsError] = useState("");
  const [swapping, setSwapping] = useState<string | null>(null);
  const [swapError, setSwapError] = useState("");

  const editable = slot.swappable && slot.status !== "passed";
  const showOptions = editable && canSwap && pathwayId !== null;
  const kind = kindLabel(slot);

  useEffect(() => {
    if (codes.length === 0) return;
    let alive = true;
    api
      .courses(codes)
      .then((r) => alive && setDetails(r.courses))
      .catch(() => alive && setDetails({}));
    return () => {
      alive = false;
    };
  }, [codes]);

  useEffect(() => {
    if (!showOptions || pathwayId === null) return;
    let alive = true;
    api
      .options(pathwayId, slot.slot_id, debounced)
      .then((r) => {
        if (!alive) return;
        setLoaded({ q: debounced, items: r.candidates });
        setOptionsError("");
      })
      .catch((e) => {
        if (!alive) return;
        setOptionsError(e instanceof ApiError ? e.message : "We couldn't load options right now.");
        setLoaded({ q: debounced, items: [] });
      });
    return () => {
      alive = false;
    };
  }, [showOptions, pathwayId, slot.slot_id, debounced]);

  const loading = showOptions && (loaded === null || loaded.q !== debounced);

  async function choose(code: string) {
    if (pathwayId === null) return;
    setSwapping(code);
    setSwapError("");
    try {
      onSwapped(await api.swap(pathwayId, slot.slot_id, code), slot.slot_id);
    } catch (e) {
      setSwapError(e instanceof ApiError ? e.message : "We couldn't make that change. Please try again.");
      setSwapping(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted">{slotCodes(slot) || kind || "Open slot"}</p>
          <h2 className="mt-1 font-serif text-3xl leading-tight text-purple">{slot.title}</h2>
          <p className="mt-2 text-sm text-muted">
            {fmtUnits(slot.units)} units{kind && slotCodes(slot) ? ` · ${kind}` : ""}
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-2 text-muted transition hover:bg-purple-soft hover:text-purple">
          ✕
        </button>
      </div>

      {slot.status === "passed" && <p className="rounded-2xl bg-purple-soft/60 px-4 py-3 text-sm text-purple">You&apos;ve completed this course. ✓</p>}

      {slot.status === "replaced" && applied?.reason && (
        <div className="rounded-2xl bg-gradient-to-br from-gold-soft to-white px-4 py-3 ring-1 ring-gold/30">
          <p className="flex items-center gap-1.5 text-xs font-medium text-[#7a6a3c]">
            <Sparkle size={13} /> Why this was picked
          </p>
          <p className="mt-1 text-sm leading-relaxed text-ink">{applied.reason}</p>
        </div>
      )}

      {codes.length === 0 && slot.swappable && <p className="text-sm text-muted">This is an open requirement — choose a course for it below.</p>}

      {codes.map((code) => {
        const d = details?.[code];
        return (
          <section key={code}>
            {codes.length > 1 && <h3 className="font-serif text-lg">{d ? `${code} · ${d.title}` : code}</h3>}
            {details === null && <div className="mt-2 h-16 animate-shimmer rounded-2xl bg-gradient-to-r from-purple-soft/40 via-white to-purple-soft/40 bg-[length:200%_100%]" />}
            {d?.description && <p className="mt-2 text-[15px] leading-relaxed text-ink/90">{d.description}</p>}
            {d?.prereq_text && (
              <p className="mt-3 text-sm text-muted">
                <span className="font-medium text-ink/80">Prerequisites · </span>
                {d.prereq_text}
              </p>
            )}
            {d && d.attributes.length > 0 && (
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {d.attributes.map((a) => (
                  <li key={a} className="rounded-full bg-purple-soft/70 px-2.5 py-0.5 text-xs text-purple">
                    {a}
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}

      {isGeSlot(slot) && ge && (
        <section aria-label="GE courses" className="space-y-4">
          {ge.hint && !ge.done && <p className="rounded-2xl bg-gold-soft px-4 py-3 text-sm text-[#6b5a2a]">{ge.hint}</p>}
          {ge.done && <p className="rounded-2xl bg-purple-soft/60 px-4 py-3 text-sm text-purple">You marked this requirement as completed. ✓</p>}
          <Button variant={ge.done ? "ghost" : "soft"} onClick={ge.onToggle}>
            {ge.done ? "Undo" : "Mark as completed"}
          </Button>
          <h3 className="font-serif text-xl text-purple">Courses that count</h3>
          <GeList areas={geAreas(slot.title)} />
        </section>
      )}

      {editable && (
        <section aria-label="Other options">
          <h3 className="font-serif text-xl text-purple">Other options</h3>
          {!showOptions ? (
            <p className="mt-2 text-sm text-muted">Course options unlock when your roadmap has finished building.</p>
          ) : (
            <>
              <input
                aria-label="Search options"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by topic, e.g. databases"
                className="mt-3 w-full rounded-full border border-line bg-white/80 px-4 py-2.5 text-sm outline-none transition focus:border-purple/40 focus:ring-4 focus:ring-purple-soft"
              />
              {optionsError && (
                <p role="alert" className="mt-3 rounded-2xl bg-gold-soft px-4 py-3 text-sm text-[#6b5a2a]">
                  {optionsError}
                </p>
              )}
              {swapError && (
                <p role="alert" className="mt-3 rounded-2xl bg-gold-soft px-4 py-3 text-sm text-[#6b5a2a]">
                  {swapError}
                </p>
              )}
              <ul className="mt-4 flex flex-col gap-3">
                {loading && [0, 1, 2].map((i) => <li key={i} className="h-24 animate-shimmer rounded-2xl bg-gradient-to-r from-purple-soft/40 via-white to-purple-soft/40 bg-[length:200%_100%]" />)}
                {!loading && loaded && loaded.items.length === 0 && !optionsError && <li className="text-sm text-muted">No other courses fit this slot right now.</li>}
                {!loading &&
                  loaded?.items.map((c) => (
                    <li key={c.code} className="rounded-2xl border border-line bg-white/80 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[11px] font-medium uppercase tracking-wider text-muted">
                            {c.code} · {fmtUnits(c.units)} units
                          </p>
                          <p className="mt-0.5 font-serif text-[1.02rem] leading-snug">{c.title}</p>
                        </div>
                        <div aria-hidden="true" className="mt-1 h-1.5 w-14 shrink-0 overflow-hidden rounded-full bg-purple-soft" title="How closely it matches">
                          <div className="h-full rounded-full bg-gradient-to-r from-gold to-purple" style={{ width: `${Math.max(8, Math.round(c.similarity * 100))}%` }} />
                        </div>
                      </div>
                      {c.summary && <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted">{c.summary}</p>}
                      {c.warnings.map((w) => (
                        <p key={w} className="mt-1.5 text-xs text-[#7a6a3c]">
                          {w}
                        </p>
                      ))}
                      <Button variant="soft" className="mt-3 !px-4 !py-1.5 text-xs" aria-label={`Use ${c.code}`} disabled={swapping !== null} onClick={() => void choose(c.code)}>
                        {swapping === c.code ? "Switching…" : "Use this course"}
                      </Button>
                    </li>
                  ))}
              </ul>
            </>
          )}
        </section>
      )}
    </div>
  );
}
