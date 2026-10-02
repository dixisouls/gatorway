import type { AppliedEdit, Term } from "./types";

export const CARD_STAGGER = 0.045; // seconds between cards appearing
export const SWAP_STAGGER = 0.5; // seconds between AI picks landing

const ordered = (terms: Term[]) => [...terms].sort((a, b) => a.position - b.position);

/** slot_id -> seconds to wait before it appears: the whole roadmap fills in order, term by term. */
export function revealDelays(terms: Term[]): Record<string, number> {
  const out: Record<string, number> = {};
  let i = 0;
  for (const term of ordered(terms)) for (const slot of term.slots) out[slot.slot_id] = i++ * CARD_STAGGER;
  return out;
}

/** slot_id -> seconds before an AI pick replaces the baseline course, in roadmap order. */
export function swapDelays(terms: Term[], applied: AppliedEdit[]): Record<string, number> {
  const picked = new Set(applied.map((a) => a.slot_id));
  const out: Record<string, number> = {};
  let i = 0;
  for (const term of ordered(terms)) {
    for (const slot of term.slots) if (picked.has(slot.slot_id)) out[slot.slot_id] = 0.3 + i++ * SWAP_STAGGER;
  }
  return out;
}
