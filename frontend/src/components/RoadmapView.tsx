"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { readChoices, readSet, writeChoices, writeSet } from "@/lib/choices";
import { api } from "@/lib/api";
import { creditHint, geAreas, isGeSlot } from "@/lib/ge";
import { fmtUnits, shortRoadmapName } from "@/lib/format";
import type { SavedPathway } from "@/lib/types";
import { usePathwayRun, type RunSpec } from "@/lib/usePathwayRun";
import { CourseDrawer } from "./CourseDrawer";
import { InterestForm } from "./InterestForm";
import { Roadmap } from "./Roadmap";
import { RotatingWords } from "./RotatingWords";
import { ScreenShimmer } from "./ScreenShimmer";
import { Button } from "./ui/Button";
import { Sparkle } from "./ui/Sparkle";

const SHIMMER_MS = 1300; // how long the finishing shimmer stays
const SHIMMER_REVEAL_MS = 450; // when, mid-sweep, the picks replace the baseline cards
const MAX_AVOID = 20; // the server accepts at most this many

export const personalisePhrases = (interest: string) => [
  "Reading your roadmap",
  `Finding electives for “${interest}”`,
  "Checking prerequisites",
  "Weighing the options",
  "Polishing the picks",
];

interface Props {
  spec: RunSpec;
  onRerun: (next: Omit<RunSpec, "key">) => void;
  onOpenHistory: () => void;
  onAddTranscript?: () => void; // offered when no transcript is on file
}

export function RoadmapView({ spec, onRerun, onOpenHistory, onAddTranscript }: Props) {
  const run = usePathwayRun(spec);
  const { result, baseline } = run;
  const pathway = result?.pathway ?? baseline;
  const interest = spec.interest ?? result?.interest ?? null;
  const [openId, setOpenId] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [revealed, setRevealed] = useState<ReadonlySet<string>>(new Set());
  const [shimmer, setShimmer] = useState(false);
  const choiceKey = `gatorway.choices.${spec.programId}.${spec.roadmapId ?? "default"}`;
  const [choices, setChoices] = useState<Record<string, string>>(() => readChoices(choiceKey));
  const doneKey = `gatorway.done.${spec.programId}.${spec.roadmapId ?? "default"}`;
  const [done, setDone] = useState<ReadonlySet<string>>(() => readSet(doneKey));
  const [creditAreas, setCreditAreas] = useState<string[]>([]);
  const [courseCount, setCourseCount] = useState<number | null>(null);

  // GE credit lines on the transcript ("GE 4") hint at which GE rows may already be met.
  useEffect(() => {
    let alive = true;
    api
      .myCourses()
      .then((r) => {
        if (!alive) return;
        setCourseCount(r.count);
        setCreditAreas([...new Set(r.courses.filter((c) => c.flagged).flatMap((c) => geAreas(c.code)))]);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // When personalising finishes: a full-screen shimmer plays and, mid-sweep, the picks replace the baseline cards. Saved roadmaps skip it.
  const shimmered = useRef<number | null>(null);
  useEffect(() => {
    if (!result || spec.saved) return;
    const ids = result.applied.map((a) => a.slot_id);
    const reveal = () => setRevealed((prev) => new Set([...prev, ...ids]));
    if (shimmered.current === result.id || !spec.interest) {
      const t = setTimeout(reveal, 0); // a manual swap, or a run with no interest: no show
      return () => clearTimeout(t);
    }
    shimmered.current = result.id;
    const timers = [setTimeout(() => setShimmer(true), 0), setTimeout(reveal, SHIMMER_REVEAL_MS), setTimeout(() => setShimmer(false), SHIMMER_MS)];
    return () => timers.forEach(clearTimeout);
  }, [result, spec.saved, spec.interest]);

  const appliedMap = useMemo(() => new Map((result?.applied ?? []).map((a) => [a.slot_id, a])), [result]);
  const baselineSlots = useMemo(() => Object.fromEntries((baseline?.terms ?? []).flatMap((t) => t.slots).map((s) => [s.slot_id, s])), [baseline]);
  const openSlot = useMemo(() => pathway?.terms.flatMap((t) => t.slots).find((s) => s.slot_id === openId) ?? null, [pathway, openId]);

  const settled = run.phase === "done" || run.phase === "error";
  const personalising = run.phase === "personalising" && !!spec.interest;

  function toggleDone(slotId: string) {
    setDone((prev) => {
      const next = new Set(prev);
      if (!next.delete(slotId)) next.add(slotId);
      writeSet(doneKey, next);
      return next;
    });
  }

  function onSwapped(updated: SavedPathway, slotId: string) {
    run.replaceResult(updated);
    setRevealed((prev) => new Set(prev).add(slotId)); // a swap you made lands at once
    setOpenId(null);
  }

  function refresh() {
    if (!pathway) return;
    onRerun({ programId: pathway.program_id, roadmapId: pathway.roadmap_id, interest, fresh: true, avoid: (result?.applied ?? []).map((a) => a.new_course_code).slice(0, MAX_AVOID) });
  }

  return (
    <div>
      {pathway ? (
        <motion.header initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="roadmap-header">
          <p className="text-sm text-muted">{shortRoadmapName(pathway.roadmap_name, pathway.program_title)}</p>
          <h1 className="mt-3 text-3xl font-medium leading-tight tracking-tight text-ink sm:text-4xl">{pathway.program_title}</h1>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
            <span className="inline-flex max-w-full items-center gap-1.5 break-words rounded-lg bg-purple-soft px-3 py-1.5 text-purple">
              {interest ? (
                <>
                  <Sparkle size={13} /> Tuned for “{interest}”
                </>
              ) : (
                "Standard roadmap"
              )}
            </span>
            {pathway.total_units_required && <span className="rounded-full bg-white/80 px-3 py-1 text-muted ring-1 ring-line">{fmtUnits(pathway.total_units_required)} units to graduate</span>}
          </div>
          {courseCount === 0 && onAddTranscript && (
            <p className="mt-4 inline-flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-white/70 px-4 py-2.5 text-sm text-muted ring-1 ring-line">
              <span>Exploring without a transcript — nothing is marked completed.</span>
              <button type="button" onClick={onAddTranscript} className="font-medium text-purple underline-offset-4 hover:underline">
                Add a transcript
              </button>
            </p>
          )}
          <div className="mt-5 flex flex-wrap gap-2">
            <Button variant="soft" onClick={onOpenHistory}>
              Past roadmaps
            </Button>
            {interest && settled && (
              <Button variant="soft" onClick={refresh}>
                Refresh picks
              </Button>
            )}
            <Button onClick={() => setAsking((v) => !v)}>
              <Sparkle size={14} /> New interest
            </Button>
          </div>
          <div className="roadmap-meta" aria-label="Roadmap overview">
            <div><strong>{pathway.terms.filter((term) => term.slots.length > 0).length}</strong> semesters</div>
            <div><strong>{pathway.terms.flatMap((term) => term.slots).filter((slot) => slot.status === "passed" || done.has(slot.slot_id)).length}</strong> marked complete</div>
            <div><strong>{result?.applied.length ?? 0}</strong> course picks</div>
          </div>
          <AnimatePresence>
            {asking && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <div className="mt-5 rounded-md border border-line bg-white/70 p-5 ">
                  <InterestForm
                    initial={interest ?? ""}
                    submitLabel="Build it"
                    skipLabel="Cancel"
                    onSkip={() => setAsking(false)}
                    onSubmit={(text) => {
                      setAsking(false);
                      onRerun({ programId: pathway.program_id, roadmapId: pathway.roadmap_id, interest: text });
                    }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.header>
      ) : (
        run.phase !== "error" && (
          <div aria-busy="true" className="flex flex-col items-center gap-4 py-24 text-center">
            <Sparkle size={40} spin />
            <p className="font-serif text-2xl text-purple">Preparing your roadmap…</p>
          </div>
        )
      )}

      <AnimatePresence>
        {personalising && (
          <motion.div
            key="working"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="mb-6 inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-gold-soft to-purple-soft px-4 py-2 text-sm text-ink ring-1 ring-gold/30"
          >
            <Sparkle size={15} spin /> <RotatingWords compact phrases={personalisePhrases(spec.interest ?? "")} />
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>{shimmer && <ScreenShimmer key="shimmer" />}</AnimatePresence>
      {run.phase === "done" && spec.interest && !spec.saved && (
        <p role="status" className="ready-notice">
          <span aria-hidden="true">✓</span>
          {result?.note
            ? "Your roadmap is ready. See the note below for details."
            : result?.applied.length
              ? "Your personalized roadmap is ready. Explore your picks below."
              : "Your roadmap is ready. Review the plan and any notes below."}
        </p>
      )}

      {run.phase === "error" && run.error && (
        <div role="alert" className="mb-6 flex flex-wrap items-center gap-3 rounded-md bg-gold-soft px-5 py-4 text-sm text-[#6b5a2a]">
          <span className="flex-1">{run.error}</span>
          <Button variant="soft" onClick={run.retry}>
            Try again
          </Button>
        </div>
      )}
      {result?.note && <p className="mb-6 rounded-md bg-gold-soft px-5 py-4 text-sm text-[#6b5a2a]">{result.note}</p>}
      {result && result.warnings.length > 0 && (
        <details className="mb-6 rounded-md bg-white/70 px-5 py-3 text-sm text-muted ring-1 ring-line">
          <summary className="cursor-pointer">Things to double-check ({result.warnings.length})</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </details>
      )}

      {pathway && (
        <Roadmap
          pathway={pathway}
          baselineSlots={baselineSlots}
          applied={appliedMap}
          isRevealed={(id) => !!spec.saved || revealed.has(id)}
          generating={personalising}
          onOpen={(s) => setOpenId(s.slot_id)}
          done={done}
          onToggleDone={toggleDone}
          creditAreas={creditAreas}
          choices={choices}
          onChoose={(headerId, code) =>
            setChoices((prev) => {
              const next = { ...prev, [headerId]: code };
              writeChoices(choiceKey, next);
              return next;
            })
          }
        />
      )}

      <CourseDrawer
        slot={openSlot}
        applied={openSlot ? appliedMap.get(openSlot.slot_id) : undefined}
        pathwayId={result?.id ?? null}
        canSwap={run.phase === "done" && result !== null}
        onClose={() => setOpenId(null)}
        onSwapped={onSwapped}
        ge={openSlot && isGeSlot(openSlot) ? { done: done.has(openSlot.slot_id), onToggle: () => toggleDone(openSlot.slot_id), hint: creditHint(openSlot, creditAreas) } : undefined}
      />
    </div>
  );
}
