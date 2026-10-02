import { creditKind, fmtUnits, groupByTerm, kindLabel, relativeDate, shortRoadmapName, slotCodes, termUnits } from "@/lib/format";
import type { Slot, Term } from "@/lib/types";

const slot = (over: Partial<Slot> = {}): Slot => ({
  slot_id: "s", codes: ["CSC 101"], title: "Intro", units: 3, slot_kind: "fixed", swappable: false,
  pool_section_id: null, counts_toward_major: false, status: "planned", ...over,
});

test("units drop a trailing .0", () => {
  expect(fmtUnits(3)).toBe("3");
  expect(fmtUnits(1.5)).toBe("1.5");
});

test("a lecture-and-lab pair reads as one line; an open slot has no codes", () => {
  expect(slotCodes(slot({ codes: ["PHYS 220", "PHYS 222"] }))).toBe("PHYS 220 + PHYS 222");
  expect(slotCodes(slot({ codes: [] }))).toBe("");
});

test("labels the kind of slot a student can recognise", () => {
  expect(kindLabel(slot({ slot_kind: "major_elective" }))).toBe("Major elective");
  expect(kindLabel(slot({ slot_kind: "free_elective" }))).toBe("Free elective");
  expect(kindLabel(slot({ codes: [], title: "GE Area 4: Social and Behavioral Science" }))).toBe("General education");
  expect(kindLabel(slot())).toBeNull();
});

test("a term's units add up", () => {
  const term: Term = { position: 0, label: "First", slots: [slot({ units: 3 }), slot({ slot_id: "t", units: 4 })] };
  expect(termUnits(term)).toBe(7);
});

test("dates read the way people say them", () => {
  const now = new Date("2026-10-10T12:00:00Z");
  expect(relativeDate("2026-10-10T08:00:00Z", now)).toBe("Today");
  expect(relativeDate("2026-10-09T08:00:00Z", now)).toBe("Yesterday");
  expect(relativeDate("2026-10-07T08:00:00Z", now)).toBe("3 days ago");
  expect(relativeDate("2026-08-01T08:00:00Z", now)).toMatch(/Aug/);
});

test("roadmap names drop the repeated program title and the word Roadmap", () => {
  const program = "Bachelor of Science in Computer Science";
  expect(shortRoadmapName(`${program} Roadmap - Quantitative Reasoning Category 1/2`, program)).toBe("Quantitative Reasoning Category 1/2");
  expect(shortRoadmapName(`${program} – COMP Associate Degree for Transfer (ADT) Roadmap`, program)).toBe("COMP Associate Degree for Transfer (ADT) Roadmap");
  expect(shortRoadmapName(`${program} Roadmap`, program)).toBe("Standard roadmap");
});

test("transcript courses group by term, oldest first, with unknown terms last", () => {
  const c = (code: string, term: string | null) => ({ code, grade: "A", term, flagged: false });
  const groups = groupByTerm([c("CSC 220", "Spring 2024"), c("CSC 101", "Fall 2023"), c("MATH 226", "Fall 2023"), c("ART 1", null), c("X 1", "Summer 2023")]);
  expect(groups.map((g) => g.term)).toEqual(["Summer 2023", "Fall 2023", "Spring 2024", "Other"]);
  expect(groups[1].courses.map((x) => x.code)).toEqual(["CSC 101", "MATH 226"]);
});

test("transcript lines the catalog cannot match are described, not called errors", () => {
  const c = (code: string, flagged = true) => ({ code, title: null, grade: "A", term: null, flagged });
  expect(creditKind(c("GE 4"))).toBe("GE credit");
  expect(creditKind(c("ENGL 1A"))).toBe("Transfer credit");
  expect(creditKind(c("ENGL 1X1"))).toBe("Transfer credit");
  expect(creditKind(c("XYZ 100"))).toBe("Not in the SFSU catalog");
  expect(creditKind(c("CSC 101", false))).toBeNull();
});
