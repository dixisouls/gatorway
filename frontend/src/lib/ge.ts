import type { Slot } from "./types";

/** The GE areas a roadmap row ("GE Area 5UD or 2UD: ...") or a transcript credit line ("GE 4") names. */
export function geAreas(text: string): string[] {
  if (!/^\s*GE\b/i.test(text)) return [];
  const head = text.split(":")[0];
  return [...head.matchAll(/\b([1-6][A-C]?(?:UD)?)\b/gi)].map((m) => m[1].toUpperCase());
}

/** An open requirement row about general education (no course picked yet). */
export const geLabel = (slot: Slot) => slot.label || slot.title;

/** A GE requirement row: open, or filled by a course the student chose for it (it keeps its requirement wording). */
export const isGeSlot = (slot: Slot) => /^\s*GE\b/i.test(geLabel(slot)) && (slot.slot_kind === "ge" || slot.codes.length === 0);

/** "You have GE 4 credit on your transcript" when the transcript has credit for an area this row names. */
export function creditHint(slot: Slot, creditAreas: string[]): string | undefined {
  if (!isGeSlot(slot)) return undefined;
  const matched = geAreas(geLabel(slot)).filter((a) => creditAreas.includes(a));
  return matched.length ? `You have GE ${matched.join(" + ")} credit on your transcript` : undefined;
}
