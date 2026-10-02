import type { Slot, Term, TranscriptCourse } from "./types";

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

const SEASON: Record<string, number> = { winter: 0, spring: 1, summer: 2, fall: 3 };

function termRank(term: string): number {
  const m = /^(winter|spring|summer|fall)\s+(\d{4})$/i.exec(term.trim());
  return m ? Number(m[2]) * 10 + SEASON[m[1].toLowerCase()] : Number.POSITIVE_INFINITY;
}

/** Transcript courses grouped by term, oldest first; courses with no term go last under "Other". */
export function groupByTerm(courses: TranscriptCourse[]): { term: string; courses: TranscriptCourse[] }[] {
  const groups = new Map<string, TranscriptCourse[]>();
  for (const c of courses) {
    const key = c.term?.trim() || "Other";
    groups.set(key, [...(groups.get(key) ?? []), c]);
  }
  return [...groups.entries()]
    .map(([term, list]) => ({ term, courses: list }))
    .sort((a, b) => termRank(a.term) - termRank(b.term) || a.term.localeCompare(b.term));
}
