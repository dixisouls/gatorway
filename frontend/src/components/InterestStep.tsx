"use client";

import { InterestForm } from "./InterestForm";

export function InterestStep({ programTitle, onSubmit }: { programTitle: string; onSubmit: (interest: string | null) => void }) {
  return (
    <div className="mx-auto max-w-xl text-center">
      <h1 className="font-serif text-4xl text-purple">What are you drawn to?</h1>
      <p className="mx-auto mt-3 max-w-md text-muted">
        Tell us a topic or career you&apos;re curious about and we&apos;ll tune the electives in <span className="text-ink">{programTitle}</span> toward it. Or skip — you can always add one later.
      </p>
      <div className="mt-10 rounded-[2rem] border border-line bg-white/70 p-6 shadow-soft backdrop-blur sm:p-8">
        <InterestForm onSubmit={(i) => onSubmit(i)} onSkip={() => onSubmit(null)} />
      </div>
    </div>
  );
}
