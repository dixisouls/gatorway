import type { Slot, Term, TranscriptCourse } from "./types";

export const fmtUnits = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

export const slotCodes = (slot: Slot) => slot.codes.join(" + ");

export function kindLabel(slot: Slot): string | null {
  if (slot.slot_kind === "ge") return "General education";
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

/** "Fall 2023", "SP2025", "2023 Fall" or "Transfer credit": the things a transcript uses as a term heading. */
export const isTermLabel = (t: string) =>
  /^(fall|spring|summer|winter)\s+\d{4}$/i.test(t) || /^(fa|sp|spr|su|sum|wi|win)\s?\d{2,4}$/i.test(t) || /^\d{4}\s+(fall|spring|summer|winter)$/i.test(t) || /^transfer( credit)?$/i.test(t);

const SEASON: Record<string, number> = { winter: 0, spring: 1, summer: 2, fall: 3 };

const ABBREVIATIONS: Record<string, number> = { fa: 3, sp: 1, spr: 1, su: 2, sum: 2, wi: 0, win: 0 };

/** Chronological sort key: real terms by year then season, then transfer credit, then everything else. */
function termRank(term: string): number {
  if (/^transfer/i.test(term)) return 1e9;
  const m = /^([a-z]{2,6})\s?(\d{2,4})$/i.exec(term) ?? /^(\d{4})\s+([a-z]{2,6})$/i.exec(term);
  if (!m) return 2e9;
  const [season, year] = /^\d/.test(m[1]) ? [m[2], m[1]] : [m[1], m[2]];
  const order = SEASON[season.toLowerCase()] ?? ABBREVIATIONS[season.toLowerCase()];
  if (order === undefined) return 2e9;
  return (year.length === 2 ? 2000 + Number(year) : Number(year)) * 10 + order;
}

/** Transcript courses grouped by term, oldest first; courses with no term go last under "Other". */
export function groupByTerm(courses: TranscriptCourse[]): { term: string; courses: TranscriptCourse[] }[] {
  const groups = new Map<string, TranscriptCourse[]>();
  for (const c of courses) {
    const term = c.term?.trim();
    const key = term && isTermLabel(term) ? term : "Other"; // an ID label or a placeholder is not a semester
    groups.set(key, [...(groups.get(key) ?? []), c]);
  }
  return [...groups.entries()]
    .map(([term, list]) => ({ term, courses: list }))
    .sort((a, b) => termRank(a.term) - termRank(b.term) || a.term.localeCompare(b.term));
}

export type CreditKind = "GE credit" | "Transfer credit" | "Not in the SFSU catalog";

/** What an unmatched transcript line most likely is: a GE credit line, transfer credit (community-college style codes), or neither. */
export function creditKind(c: TranscriptCourse): CreditKind | null {
  if (!c.flagged) return null;
  if (/^\s*GE\b/i.test(c.code)) return "GE credit";
  const number = c.code.trim().split(/\s+/).pop() ?? "";
  return /x/i.test(number) || number.replace(/\D/g, "").length < 3 ? "Transfer credit" : "Not in the SFSU catalog";
}
