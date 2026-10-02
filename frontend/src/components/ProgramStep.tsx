"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { shortRoadmapName } from "@/lib/format";
import type { ProgramBrief, RoadmapBrief } from "@/lib/types";
import { useDebounced } from "@/lib/useDebounced";
import { Button } from "./ui/Button";

export interface ChosenProgram {
  id: number;
  title: string;
  roadmapId: number | null;
}

const LEVELS = [
  { label: "All", value: "" },
  { label: "Undergraduate", value: "undergraduate" },
  { label: "Graduate", value: "graduate" },
  { label: "Minor", value: "minor" },
  { label: "Certificate", value: "certificate" },
];

export function ProgramStep({ onChosen }: { onChosen: (p: ChosenProgram) => void }) {
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const debounced = useDebounced(query, 250);
  const [programs, setPrograms] = useState<ProgramBrief[] | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<ProgramBrief | null>(null);
  const [roadmaps, setRoadmaps] = useState<RoadmapBrief[] | null>(null); // null while loading
  const [roadmapId, setRoadmapId] = useState<number | null>(null);
  const latestPick = useRef(0);

  useEffect(() => {
    let alive = true;
    api
      .programs(debounced, level)
      .then((r) => {
        if (!alive) return;
        setPrograms(r.programs);
        setError("");
      })
      .catch(() => alive && setError("We couldn't load programs. Check your connection and try again."));
    return () => {
      alive = false;
    };
  }, [debounced, level]);

  function choose(p: ProgramBrief) {
    const pick = ++latestPick.current;
    setSelected(p);
    setRoadmaps(null);
    setRoadmapId(null);
    api
      .roadmaps(p.id)
      .then((r) => {
        if (pick !== latestPick.current) return; // the student already picked something else
        setRoadmaps(r.roadmaps);
        setRoadmapId((r.roadmaps.find((x) => x.is_default) ?? r.roadmaps[0])?.id ?? null);
      })
      .catch(() => {
        if (pick !== latestPick.current) return;
        setRoadmaps([]);
        setError("We couldn't load that program's roadmaps. Please try again.");
      });
  }

  function changeProgram() {
    latestPick.current += 1; // ignore a roadmap response still in flight for the old choice
    setSelected(null);
    setRoadmaps(null);
    setRoadmapId(null);
    setError("");
  }

  const noRoadmap = selected !== null && roadmaps !== null && roadmaps.length === 0;

  return (
    <div className="step-content">
      <h1 className="step-heading">Find your field.</h1>
      <p className="step-description">Choose the program you’re working toward. We’ll build from its official degree roadmap.</p>

      <div className="step-panel">
        {selected ? (
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-wider text-muted">Your program</p>
              <p className="mt-1 text-lg text-ink">{selected.title}</p>
              <p className="mt-1 text-xs text-muted">{[selected.degree_type, selected.college].filter(Boolean).join(" · ")}</p>
            </div>
            <button type="button" onClick={changeProgram} className="shrink-0 text-sm text-muted transition hover:text-purple">
              Change program
            </button>
          </div>
        ) : (
          <>
        <input
          aria-label="Search programs"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search programs, e.g. computer science"
          className="w-full rounded-md border border-line bg-white/80 px-4 py-3 text-[15px] outline-none transition focus:border-purple/40 focus:ring-4 focus:ring-purple-soft"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {LEVELS.map((l) => (
            <button
              key={l.value}
              type="button"
              aria-pressed={level === l.value}
              onClick={() => setLevel(l.value)}
              className={`rounded-full px-3 py-1 text-xs transition ${level === l.value ? "bg-purple text-white" : "bg-purple-soft/70 text-purple hover:bg-purple-soft"}`}
            >
              {l.label}
            </button>
          ))}
        </div>

        {error && (
          <p role="alert" className="mt-4 rounded-md bg-gold-soft px-4 py-3 text-sm text-[#6b5a2a]">
            {error}
          </p>
        )}

        <ul className="mt-6 max-h-[26rem] overflow-y-auto pr-1">
          {programs === null && !error && <li className="h-12 animate-shimmer rounded-md bg-gradient-to-r from-purple-soft/40 via-white to-purple-soft/40 bg-[length:200%_100%]" />}
          {programs?.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted">No programs match that search.</li>}
          {programs?.map((p) => (
            <li key={p.id}>
              <button type="button" onClick={() => choose(p)} className="program-row w-full px-3 py-4 text-left transition hover:bg-purple-soft/50">
                <span className="flex items-start justify-between gap-4 text-[15px] text-ink">{p.title}<span aria-hidden="true">↗</span></span>
                <span className="mt-1.5 block text-xs text-muted">{[p.degree_type, p.college].filter(Boolean).join(" · ")}</span>
              </button>
            </li>
          ))}
        </ul>
          </>
        )}

        <AnimatePresence>
          {selected && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
              <div className="mt-5 border-t border-line pt-5">
                {roadmaps === null && <p className="text-sm text-muted">Finding roadmaps…</p>}
                {noRoadmap && <p className="text-sm text-muted">This program doesn&apos;t have a published roadmap yet. Pick another to continue.</p>}
                {roadmaps !== null && roadmaps.length > 1 && (
                  <fieldset>
                    <legend className="mb-2 text-sm text-muted">Which roadmap?</legend>
                    <div className="flex flex-col gap-2">
                      {roadmaps.map((r) => (
                        <label key={r.id} className={`flex cursor-pointer items-center gap-3 rounded-md px-4 py-2.5 text-sm transition ${roadmapId === r.id ? "bg-gold-soft ring-1 ring-gold/40" : "hover:bg-purple-soft/50"}`}>
                          <input type="radio" name="roadmap" checked={roadmapId === r.id} onChange={() => setRoadmapId(r.id)} className="accent-ink" />
                          {shortRoadmapName(r.name, selected.title)}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mt-6 flex justify-end">
          <Button disabled={!selected || roadmapId === null} onClick={() => selected && onChosen({ id: selected.id, title: selected.title, roadmapId })}>
            Continue
          </Button>
        </div>
      </div>
    </div>
  );
}
