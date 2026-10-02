import type { Slot, Term } from "./types";

export const fmtUnits = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

export const slotCodes = (slot: Slot) => slot.codes.join(" + ");

export function kindLabel(slot: Slot): string | null {
  if (slot.slot_kind === "major_elective") return "Major elective";
  if (slot.slot_kind === "free_elective") return "Free elective";
  if (/^GE\b|general education/i.test(slot.title)) return "General education";
  return null;
}

export const termUnits = (term: Term) => term.slots.reduce((sum, s) => sum + s.units, 0);

export function relativeDate(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const days = Math.floor((now.getTime() - then.getTime()) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return then.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function shortRoadmapName(name: string, programTitle: string): string {
  let n = name.startsWith(programTitle) ? name.slice(programTitle.length) : name;
  n = n.replace(/^[\s–—:-]+/, "").replace(/^Roadmap[\s–—:-]*/i, "").trim();
  return n || "Standard roadmap";
}
