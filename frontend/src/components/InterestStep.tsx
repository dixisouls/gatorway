"use client";

import { InterestForm } from "./InterestForm";

export function InterestStep({ programTitle, onSubmit }: { programTitle: string; onSubmit: (interest: string | null) => void }) {
  return (
    <div className="step-content">
      <h1 className="step-heading">Follow your curiosity.</h1>
      <p className="step-description">
        Tell us a topic or career you&apos;re curious about and we&apos;ll tune the electives in <span className="text-ink">{programTitle}</span> toward it. Or skip — you can always add one later.
      </p>
      <div className="step-panel">
        <InterestForm onSubmit={(i) => onSubmit(i)} onSkip={() => onSubmit(null)} />
      </div>
    </div>
  );
}
