"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { readChoices, writeChoices } from "@/lib/choices";
import { fmtUnits, shortRoadmapName } from "@/lib/format";
import { swapDelays } from "@/lib/reveal";
import type { SavedPathway } from "@/lib/types";
import { usePathwayRun, type RunSpec } from "@/lib/usePathwayRun";
import { CourseDrawer } from "./CourseDrawer";
import { InterestForm } from "./InterestForm";
import { Roadmap } from "./Roadmap";
import { RotatingWords } from "./RotatingWords";
import { Button } from "./ui/Button";
import { Sparkle } from "./ui/Sparkle";

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
}

export function RoadmapView({ spec, onRerun, onOpenHistory }: Props) {
  const run = usePathwayRun(spec);
  const { result, baseline } = run;
  const pathway = result?.pathway ?? baseline;
  const interest = spec.interest ?? result?.interest ?? null;
  const [openId, setOpenId] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [revealed, setRevealed] = useState<ReadonlySet<string>>(new Set());
  const choiceKey = `gatorway.choices.${spec.programId}.${spec.roadmapId ?? "default"}`;
  const [choices, setChoices] = useState<Record<string, string>>(() => readChoices(choiceKey));

  // AI picks land one after another once the real result arrives (saved roadmaps skip the show).
  useEffect(() => {
    if (!result || spec.saved) return;
    const timers = Object.entries(swapDelays(result.pathway.terms, result.applied)).map(([id, delay]) =>
      setTimeout(() => setRevealed((prev) => new Set(prev).add(id)), delay * 1000),
    );
    return () => timers.forEach(clearTimeout);
  }, [result, spec.saved]);

  const appliedMap = useMemo(() => new Map((result?.applied ?? []).map((a) => [a.slot_id, a])), [result]);
  const baselineSlots = useMemo(() => Object.fromEntries((baseline?.terms ?? []).flatMap((t) => t.slots).map((s) => [s.slot_id, s])), [baseline]);
  const openSlot = useMemo(() => pathway?.terms.flatMap((t) => t.slots).find((s) => s.slot_id === openId) ?? null, [pathway, openId]);

  const settled = run.phase === "done" || run.phase === "error";
  const personalising = run.phase === "personalising" && !!spec.interest;

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
        <motion.header initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <p className="text-sm text-muted">{shortRoadmapName(pathway.roadmap_name, pathway.program_title)}</p>
          <h1 className="mt-1 font-serif text-4xl leading-tight text-purple sm:text-5xl">{pathway.program_title}</h1>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/80 px-3 py-1 text-muted ring-1 ring-line">
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
          <AnimatePresence>
            {asking && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <div className="mt-5 rounded-[2rem] border border-line bg-white/70 p-5 shadow-soft backdrop-blur">
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

      {run.phase === "error" && run.error && (
        <div role="alert" className="mb-6 flex flex-wrap items-center gap-3 rounded-2xl bg-gold-soft px-5 py-4 text-sm text-[#6b5a2a]">
          <span className="flex-1">{run.error}</span>
          <Button variant="soft" onClick={run.retry}>
            Try again
          </Button>
        </div>
      )}
      {result?.note && <p className="mb-6 rounded-2xl bg-gold-soft px-5 py-4 text-sm text-[#6b5a2a]">{result.note}</p>}
      {result && result.warnings.length > 0 && (
        <details className="mb-6 rounded-2xl bg-white/70 px-5 py-3 text-sm text-muted ring-1 ring-line">
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
      />
    </div>
  );
}
