import type { Slot } from "./types";

export type Item = { kind: "slot"; slot: Slot } | { kind: "choice"; header: Slot; options: Slot[] };

// The roadmap lists "Select One (Major Core):" and then its alternatives as separate rows with no units of their own.
const isHeader = (s: Slot) => s.codes.length === 0 && !s.swappable && /^\s*select\b/i.test(s.title);
const isOption = (s: Slot) => s.codes.length > 0 && s.units === 0 && s.status !== "replaced";

/** Folds each "Select One" row and the alternatives that follow it into one choice. Fewer than two alternatives is not a real choice. */
export function groupChoices(slots: Slot[]): Item[] {
  const out: Item[] = [];
  for (let i = 0; i < slots.length; i++) {
    const s = slots[i];
    if (!isHeader(s)) {
      out.push({ kind: "slot", slot: s });
      continue;
    }
    const options: Slot[] = [];
    while (i + 1 < slots.length && isOption(slots[i + 1])) options.push(slots[++i]);
    if (options.length >= 2) out.push({ kind: "choice", header: s, options });
    else out.push({ kind: "slot", slot: s }, ...options.map((o) => ({ kind: "slot" as const, slot: o })));
  }
  return out;
}
