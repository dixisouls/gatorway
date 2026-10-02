"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { creditKind, groupByTerm } from "@/lib/format";
import type { TranscriptSummary } from "@/lib/types";
import { RotatingWords } from "./RotatingWords";
import { Button } from "./ui/Button";
import { Sparkle } from "./ui/Sparkle";

export const EXTRACT_PHRASES = [
  "Opening your transcript",
  "Reading each term",
  "Finding your courses",
  "Matching your grades",
  "Checking the catalog",
  "Almost there",
];

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
type Phase = "idle" | "extracting" | "done" | "error";

export function TranscriptStep({ onDone, onSkip, minMs = 1800 }: { onDone: () => void; onSkip?: () => void; minMs?: number }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [summary, setSummary] = useState<TranscriptSummary | null>(null);
  const [saved, setSaved] = useState<TranscriptSummary | null>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    let alive = true;
    api
      .myCourses()
      .then((r) => {
        if (alive && r.count > 0) setSaved(r);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  async function upload(file: File | undefined) {
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose your transcript as a PDF file.");
      setPhase("error");
      return;
    }
    setPhase("extracting");
    setError("");
    try {
      // minMs keeps the animation from flashing past when the server is quick
      const [result] = await Promise.all([api.uploadTranscript(file), sleep(minMs)]);
      setSummary(result);
      setPhase("done");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong reading your transcript. Please try again.");
      setPhase("error");
    }
  }

  return (
    <div className="step-content">
      <h1 className="step-heading">Bring your progress with you.</h1>
      <p className="step-description">Upload your transcript so your plan starts where you are. We’ll account for the courses you’ve already taken.</p>
      <div className="step-panel">
        <AnimatePresence mode="wait">
          {phase === "idle" && (
            <motion.div key="idle" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
              <label
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  void upload(e.dataTransfer.files[0]);
                }}
                data-dragging={dragging}
                className="upload-zone flex cursor-pointer flex-col items-center justify-center gap-3 px-6 py-8 text-center transition-colors"
              >
                <input type="file" accept="application/pdf" aria-label="Transcript PDF" className="sr-only" onChange={(e) => void upload(e.target.files?.[0])} />
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.2" aria-hidden="true"><path d="M10 4h9l6 6v18H7V4h3Zm9 0v7h6M16 23V14m-4 4 4-4 4 4" /></svg>
                <span className="text-lg font-semibold tracking-tight">Drop your SFSU transcript</span>
                <span className="text-sm text-muted">or click to choose a PDF</span>
              </label>
              {saved && (
                <div className="mt-5 flex flex-col items-center gap-2 text-sm text-muted">
                  <span>We already have courses from your last upload.</span>
                  <Button variant="soft" onClick={onDone}>
                    Use my {saved.count} saved courses
                  </Button>
                </div>
              )}
              {onSkip && (
                <button type="button" onClick={onSkip} className="mx-auto mt-6 block text-sm text-muted transition hover:text-purple">
                  Skip for now — I just want to explore
                </button>
              )}
            </motion.div>
          )}

          {phase === "extracting" && (
            <motion.div
              key="extracting"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="transcript-processing"
            >
              <Sparkle size={44} spin />
              <RotatingWords phrases={EXTRACT_PHRASES} />
            </motion.div>
          )}

          {phase === "done" && summary && (
            <motion.div key="done" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border border-line bg-paper/60 p-5">
              <h2 className="text-lg font-semibold">
                We found {summary.count} {summary.count === 1 ? "course" : "courses"}
              </h2>
              <div className="mt-6 max-h-[26rem] space-y-5 overflow-y-auto pr-1">
                {groupByTerm(summary.courses).map((g, gi) => (
                  <motion.div key={g.term} role="group" aria-label={g.term} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: gi * 0.08 }}>
                    <h3 className="mb-2 px-1 font-serif text-lg text-purple">{g.term}</h3>
                    <ul className="divide-y divide-line overflow-hidden rounded-md bg-white/80 ring-1 ring-line">
                      {g.courses.map((c) => (
                        <li key={c.code} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-ink">{c.code}</span>
                            {c.title && <span className="text-muted">{c.title}</span>}
                            {creditKind(c) && <span className="rounded-full bg-gold-soft px-2 py-0.5 text-xs text-[#6b5a2a]">{creditKind(c)}</span>}
                          </span>
                          {c.grade && <span className="rounded-full bg-purple-soft/70 px-2.5 py-0.5 text-xs text-purple">{c.grade}</span>}
                        </li>
                      ))}
                    </ul>
                  </motion.div>
                ))}
              </div>
              {summary.courses.some((c) => c.flagged) && (
                <p className="mt-5 text-center text-sm text-muted">
                  Transfer and GE credit isn&apos;t matched to SFSU courses yet. On your roadmap you can mark the matching GE requirements as completed.
                </p>
              )}
              <div className="mt-8 flex justify-center">
                <Button onClick={onDone}>Continue</Button>
              </div>
            </motion.div>
          )}

          {phase === "error" && (
            <motion.div key="error" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border border-line bg-paper/60 p-5 text-center">
              <p role="alert" className="rounded-md bg-gold-soft px-4 py-3 text-sm text-[#6b5a2a]">
                {error}
              </p>
              <Button className="mt-6" onClick={() => setPhase("idle")}>
                Try again
              </Button>
              {onSkip && (
                <button type="button" onClick={onSkip} className="mx-auto mt-4 block text-sm text-muted transition hover:text-purple">
                  Skip for now — I just want to explore
                </button>
              )}

            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
