"use client";

import { AnimatePresence, motion } from "motion/react";
import { useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { RunSpec } from "@/lib/usePathwayRun";
import { HistoryPanel } from "./HistoryPanel";
import { InterestStep } from "./InterestStep";
import { ProgramStep, type ChosenProgram } from "./ProgramStep";
import { RoadmapView } from "./RoadmapView";
import { TranscriptStep } from "./TranscriptStep";
import { Aurora } from "./ui/Aurora";
import { Button } from "./ui/Button";
import { Sparkle } from "./ui/Sparkle";

type Step = "transcript" | "program" | "interest" | "roadmap";
const ORDER: Step[] = ["transcript", "program", "interest"];

function StepDots({ step }: { step: Step }) {
  const at = ORDER.indexOf(step);
  if (at < 0) return null;
  return (
    <div className="flex items-center gap-1.5" aria-label={`Step ${at + 1} of ${ORDER.length}`}>
      {ORDER.map((s, i) => (
        <motion.span key={s} animate={{ width: i === at ? 22 : 7, opacity: i <= at ? 1 : 0.35 }} className="h-[7px] rounded-full bg-purple" />
      ))}
    </div>
  );
}

export function Planner() {
  const { user, logout } = useAuth();
  const [step, setStep] = useState<Step>("transcript");
  const [program, setProgram] = useState<ChosenProgram | null>(null);
  const [spec, setSpec] = useState<RunSpec | null>(null);
  const [history, setHistory] = useState(false);
  const [notice, setNotice] = useState("");
  const counter = useRef(0);

  function start(next: Omit<RunSpec, "key">) {
    counter.current += 1;
    setSpec({ ...next, key: `run-${counter.current}` }); // a new object each run: the roadmap view restarts cleanly
    setStep("roadmap");
  }

  async function openSaved(id: number) {
    setHistory(false);
    setNotice("");
    try {
      const saved = await api.getPathway(id);
      start({ programId: saved.pathway.program_id, roadmapId: saved.pathway.roadmap_id, interest: saved.interest, saved });
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : "We couldn't open that roadmap.");
    }
  }

  return (
    <div className="relative min-h-dvh">
      <Aurora />
      <nav className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
        <span className="inline-flex items-center gap-2 font-serif text-xl text-purple">
          <Sparkle size={18} /> GatorWay
        </span>
        <StepDots step={step} />
        <div className="flex items-center gap-1 text-sm">
          {step === "roadmap" && (
            <Button variant="ghost" onClick={() => setStep("program")}>
              New roadmap
            </Button>
          )}
          <Button variant="ghost" onClick={() => setHistory(true)}>
            History
          </Button>
          <span className="hidden max-w-[10rem] truncate text-muted sm:inline">{user?.email}</span>
          <Button variant="ghost" onClick={logout}>
            Sign out
          </Button>
        </div>
      </nav>

      <main className="mx-auto max-w-5xl px-5 pb-28 pt-6 sm:px-8">
        {notice && (
          <p role="alert" className="mb-6 rounded-2xl bg-gold-soft px-5 py-3 text-sm text-[#6b5a2a]">
            {notice}
          </p>
        )}
        <AnimatePresence mode="wait">
          <motion.div key={step === "roadmap" ? spec?.key : step} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.35 }}>
            {step === "transcript" && <TranscriptStep onDone={() => setStep("program")} onSkip={() => setStep("program")} />}
            {step === "program" && <ProgramStep onChosen={(p) => { setProgram(p); setStep("interest"); }} />}
            {step === "interest" && program && (
              <InterestStep programTitle={program.title} onSubmit={(interest) => start({ programId: program.id, roadmapId: program.roadmapId, interest })} />
            )}
            {step === "roadmap" && spec && <RoadmapView spec={spec} onRerun={start} onOpenHistory={() => setHistory(true)} onAddTranscript={() => setStep("transcript")} />}
          </motion.div>
        </AnimatePresence>
      </main>

      <HistoryPanel open={history} onClose={() => setHistory(false)} onPick={(id) => void openSaved(id)} />
    </div>
  );
}
