"use client";

import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { RotatingWords } from "./RotatingWords";
import { Sparkle } from "./ui/Sparkle";

/** Presentation only: dismissing the layer leaves the existing run in progress. */
export function PersonalizationOverlay({ interest, phrases }: { interest: string; phrases: string[] }) {
  const [dismissed, setDismissed] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const dismissButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (dismissed) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    const siblings = Array.from(document.body.children)
      .filter((element): element is HTMLElement => element instanceof HTMLElement && !element.contains(panel.current))
      .map((element) => ({ element, inert: element.inert }));
    siblings.forEach(({ element }) => { element.inert = true; });
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDismissed(true);
      if (event.key === "Tab") {
        event.preventDefault();
        dismissButton.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      siblings.forEach(({ element, inert }) => { element.inert = inert; });
      if (previous?.isConnected) previous.focus();
    };
  }, [dismissed]);

  if (dismissed || typeof document === "undefined") return null;
  return createPortal(
    <motion.div ref={panel} role="dialog" aria-modal="true" aria-label="Personalizing your roadmap" tabIndex={-1}
      className="personalization-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .35 }}>
      <div className="personalization-sweep" aria-hidden="true" />
      <div className="personalization-content">
        <div className="personalization-orb" aria-hidden="true"><Sparkle size={38} spin /></div>
        <p className="eyebrow">A LITTLE MORE YOU</p>
        <h2>Connecting your interests<br />to your next chapter.</h2>
        <p className="personalization-interest">We’re shaping your electives around <strong className="font-medium text-purple">{interest}</strong>.</p>
        <div className="personalization-status"><RotatingWords compact phrases={phrases} /></div>
        <button ref={dismissButton} className="personalization-dismiss" type="button" onClick={() => setDismissed(true)}>Keep exploring while we work <span aria-hidden="true">↗</span></button>
      </div>
    </motion.div>,
    document.body,
  );
}
