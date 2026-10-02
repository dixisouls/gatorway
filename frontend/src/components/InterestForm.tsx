"use client";

import { useState } from "react";
import { Button } from "./ui/Button";
import { Sparkle } from "./ui/Sparkle";

export const SUGGESTIONS = ["Web development", "AI and machine learning", "Data and databases", "Cybersecurity", "Game design", "Entrepreneurship"];

interface Props {
  initial?: string;
  submitLabel?: string;
  skipLabel?: string;
  onSubmit: (interest: string) => void;
  onSkip?: () => void;
}

export function InterestForm({ initial = "", submitLabel = "Build my roadmap", skipLabel = "Skip — use the standard roadmap", onSubmit, onSkip }: Props) {
  const [text, setText] = useState(initial);
  const trimmed = text.trim();

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (trimmed) onSubmit(trimmed);
      }}
    >
      <label className="relative block">
        <span className="sr-only">Your interest</span>
        <Sparkle size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2" />
        <input
          aria-label="Your interest"
          value={text}
          maxLength={500}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. web development with Next.js"
          className="w-full rounded-full border border-line bg-white/80 py-3.5 pl-11 pr-5 text-[15px] outline-none transition focus:border-purple/40 focus:ring-4 focus:ring-purple-soft"
        />
      </label>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((s) => (
          <button key={s} type="button" onClick={() => setText(s)} className="rounded-full bg-purple-soft/70 px-3 py-1 text-xs text-purple transition hover:bg-purple-soft">
            {s}
          </button>
        ))}
      </div>
      <div className="mt-7 flex flex-col items-center gap-3">
        <Button type="submit" disabled={!trimmed}>
          {submitLabel}
        </Button>
        {onSkip && (
          <button type="button" onClick={onSkip} className="text-sm text-muted transition hover:text-purple">
            {skipLabel}
          </button>
        )}
      </div>
    </form>
  );
}
