"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

/** A right-hand slide-over. Closes on Escape or a click on the dimmed backdrop. */
export function Sheet({ open, onClose, label, children }: { open: boolean; onClose: () => void; label: string; children: React.ReactNode }) {
  const panel = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const elements = panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), a[href], select, textarea, [tabindex="0"]');
        const first = elements?.[0];
        const last = elements?.[elements.length - 1];
        if (!first || !last) {
          e.preventDefault();
        } else if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [open]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div
            data-testid="sheet-backdrop"
            className="absolute inset-0 bg-ink/25 backdrop-blur-[3px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            ref={panel}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label={label}
            className="absolute right-0 top-0 flex h-full w-full max-w-lg flex-col overflow-y-auto overscroll-contain border-l border-line bg-paper p-6 shadow-2xl outline-none sm:p-9"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 260, damping: 32 }}
          >
            {children}
          </motion.aside>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
