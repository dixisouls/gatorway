"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";

/** A right-hand slide-over. Closes on Escape or a click on the dimmed backdrop. */
export function Sheet({ open, onClose, label, children }: { open: boolean; onClose: () => void; label: string; children: React.ReactNode }) {
  const panel = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    panel.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div
            data-testid="sheet-backdrop"
            className="absolute inset-0 bg-ink/20 backdrop-blur-[2px]"
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
            className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col overflow-y-auto rounded-l-[2rem] bg-paper p-6 shadow-2xl outline-none sm:p-8"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 260, damping: 32 }}
          >
            {children}
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
}
