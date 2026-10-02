"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { relativeDate } from "@/lib/format";
import type { PathwayListItem } from "@/lib/types";
import { Sheet } from "./ui/Sheet";
import { Sparkle } from "./ui/Sparkle";

export function HistoryPanel({ open, onClose, onPick }: { open: boolean; onClose: () => void; onPick: (id: number) => void }) {
  const [items, setItems] = useState<PathwayListItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    let alive = true;
    api
      .listPathways()
      .then((r) => {
        if (!alive) return;
        setItems(r.pathways);
        setError("");
      })
      .catch(() => alive && setError("We couldn't load your saved roadmaps."));
    return () => {
      alive = false;
    };
  }, [open]);

  return (
    <Sheet open={open} onClose={onClose} label="Past roadmaps">
      <div className="flex items-center justify-between gap-4"><h2 className="font-serif text-3xl text-purple">Past roadmaps</h2><button type="button" aria-label="Close" onClick={onClose} className="rounded-full p-2 text-muted hover:bg-purple-soft">✕</button></div>
      <p className="mt-1 text-sm text-muted">Every roadmap you build is saved here.</p>
      {error && (
        <p role="alert" className="mt-5 rounded-md bg-gold-soft px-4 py-3 text-sm text-[#6b5a2a]">
          {error}
        </p>
      )}
      <ul className="mt-6 flex flex-col gap-3">
        {items === null && !error && [0, 1, 2].map((i) => <li key={i} className="h-20 animate-shimmer rounded-md bg-gradient-to-r from-purple-soft/40 via-white to-purple-soft/40 bg-[length:200%_100%]" />)}
        {items?.length === 0 && <li className="py-8 text-center text-sm text-muted">No saved roadmaps yet. Build one and it will appear here.</li>}
        {items?.map((it, i) => (
          <motion.li key={it.id} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
            <button type="button" onClick={() => onPick(it.id)} className="w-full rounded-md border border-line bg-white/80 p-4 text-left shadow-soft transition hover:-translate-y-0.5 hover:bg-white">
              <span className="block text-xs text-muted">{relativeDate(it.created_at)}</span>
              <span className="mt-0.5 block font-serif text-lg leading-snug">{it.program_title || "Roadmap"}</span>
              <span className="mt-2 flex items-center gap-2 text-sm text-muted">
                {it.interest ? (
                  <>
                    <Sparkle size={13} />
                    <span>{it.interest}</span>
                  </>
                ) : (
                  <span>Standard roadmap</span>
                )}
                {it.swaps > 0 && <span className="ml-auto rounded-full bg-gold-soft px-2 py-0.5 text-xs text-[#7a6a3c]">{it.swaps} picks</span>}
              </span>
            </button>
          </motion.li>
        ))}
      </ul>
    </Sheet>
  );
}
