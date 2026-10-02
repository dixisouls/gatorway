"use client";

import type { ProgramBrief, ProgramCandidate } from "@/lib/types";
import { Button } from "./ui/Button";

/** "We found this degree on your transcript: is it right?" Yes continues with it (to its roadmap options); No goes to choosing the degree. */
export function DegreeConfirm({
  raw,
  candidates,
  onYes,
  onNo,
}: {
  raw: string;
  candidates: ProgramCandidate[];
  onYes: (program: ProgramBrief) => void;
  onNo: () => void;
}) {
  const [best, ...others] = candidates;
  if (!best) return null;
  return (
    <div className="step-content">
      <h1 className="step-heading">Is this your degree?</h1>
      <p className="step-description">
        Your transcript lists <span className="text-ink">“{raw}”</span>. Here&apos;s our closest match.
      </p>
      <div className="step-panel">
        <p className="text-xs uppercase tracking-wider text-muted">Our best match</p>
        <p className="mt-1 text-lg text-ink">{best.title}</p>
        <p className="mt-1 text-xs text-muted">{[best.degree_type, best.college].filter(Boolean).join(" · ")}</p>

        {others.length > 0 && (
          <div className="mt-5 border-t border-line pt-4">
            <p className="mb-2 text-sm text-muted">Or did you mean:</p>
            <div className="flex flex-col gap-1.5">
              {others.map((p) => (
                <button key={p.id} type="button" onClick={() => onYes(p)} className="rounded-md px-3 py-2 text-left text-sm text-ink transition hover:bg-purple-soft/60">
                  {p.title}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center justify-end gap-4">
          <button type="button" onClick={onNo} className="text-sm text-muted transition hover:text-purple">
            No, let me choose
          </button>
          <Button onClick={() => onYes(best)}>Yes, that&apos;s it</Button>
        </div>
      </div>
    </div>
  );
}
