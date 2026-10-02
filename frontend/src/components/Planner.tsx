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
import { Button } from "./ui/Button";
import { Brand } from "./ui/Brand";
import { SetupGuide } from "./SetupGuide";

type Step = "transcript" | "program" | "interest" | "roadmap";
const STEPS: { key: Step; label: string; description: string }[] = [
  { key: "transcript", label: "Transcript", description: "Start with what you know." },
  { key: "program", label: "Program", description: "Choose your direction." },
  { key: "interest", label: "Interests", description: "Follow your curiosity." },
  { key: "roadmap", label: "Your roadmap", description: "Make your next move." },
];

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

  const stepIndex = STEPS.findIndex((item) => item.key === step);

  return (
    <div className="site-shell">
      <header className="site-header">
        <div className="flex items-center gap-8"><Brand /><span className="header-context hidden sm:inline">Your degree planner</span></div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => setHistory(true)}>History</Button>
          <span className="account-avatar hidden sm:grid" title={user?.email}>{user?.email?.[0]?.toUpperCase() ?? "G"}</span>
          <Button variant="ghost" onClick={logout}>Sign out</Button>
        </div>
      </header>
      <main className={step === "roadmap" ? "planner-main roadmap-main" : "planner-main"}>
        <div className="workspace-heading">
          <div><p className="eyebrow">YOUR NEXT CHAPTER</p><h2>{step === "roadmap" ? "A little direction. A lot of possibility." : "Let’s put your future in focus."}</h2></div>
          {step === "roadmap" ? <Button variant="soft" onClick={() => setStep("program")}>+ New roadmap</Button> : <span className="setup-count">Step {stepIndex + 1} of 3</span>}
        </div>
        {notice && <p role="alert" className="mb-5 rounded-xl bg-gold-soft px-5 py-3 text-sm text-[#6b5a2a]">{notice}</p>}
        <div className={step === "roadmap" ? "roadmap-workspace" : "setup-card"}>
          {step !== "roadmap" && <ol className="setup-progress" aria-label="Planning steps">
            {STEPS.slice(0, 3).map((item, index) => <li key={item.key} aria-current={step === item.key ? "step" : undefined} data-complete={index < stepIndex}>
              <span className="progress-number">{index < stepIndex ? "✓" : index + 1}</span><span>{item.label}</span>
            </li>)}
          </ol>}
          <AnimatePresence mode="wait">
            <motion.div className={step === "roadmap" ? "" : "setup-body"} key={step === "roadmap" ? spec?.key : step} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: .2 }}>
              {step !== "roadmap" && <div className="setup-form">
                {step === "transcript" && <TranscriptStep onDone={() => setStep("program")} onSkip={() => setStep("program")} />}
                {step === "program" && <ProgramStep onChosen={(p) => { setProgram(p); setStep("interest"); }} />}
                {step === "interest" && program && <InterestStep programTitle={program.title} onSubmit={(interest) => start({ programId: program.id, roadmapId: program.roadmapId, interest })} />}
              </div>}
              {step !== "roadmap" && <SetupGuide step={step} />}
              {step === "roadmap" && spec && <RoadmapView spec={spec} onRerun={start} onOpenHistory={() => setHistory(true)} onAddTranscript={() => setStep("transcript")} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
      <footer className="site-footer"><span>GatorWay · Made for your next chapter.</span><span>San Francisco State University</span></footer>
      <HistoryPanel open={history} onClose={() => setHistory(false)} onPick={(id) => void openSaved(id)} />
    </div>
  );
}
