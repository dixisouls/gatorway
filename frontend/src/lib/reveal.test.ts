import { CARD_STAGGER, revealDelays, SWAP_STAGGER, swapDelays } from "@/lib/reveal";
import type { Slot, Term } from "@/lib/types";

const slot = (id: string): Slot => ({
  slot_id: id, codes: [], title: id, units: 3, slot_kind: "fixed", swappable: false, pool_section_id: null,
  counts_toward_major: false, status: "planned",
});
const terms: Term[] = [
  { position: 1, label: "Second", slots: [slot("c"), slot("d")] },
  { position: 0, label: "First", slots: [slot("a"), slot("b")] },
];

test("the roadmap fills in term by term, card by card, whatever order the terms arrive in", () => {
  const d = revealDelays(terms);
  expect(d.a).toBe(0);
  expect(d.b).toBeCloseTo(CARD_STAGGER);
  expect(d.c).toBeCloseTo(2 * CARD_STAGGER);
  expect(d.d).toBeCloseTo(3 * CARD_STAGGER);
});

test("AI picks land one after another in roadmap order", () => {
  const d = swapDelays(terms, [
    { slot_id: "d", new_course_code: "X 1", title: "", reason: "" },
    { slot_id: "a", new_course_code: "X 2", title: "", reason: "" },
  ]);
  expect(Object.keys(d).sort()).toEqual(["a", "d"]);
  expect(d.d - d.a).toBeCloseTo(SWAP_STAGGER);
  expect(d.a).toBeGreaterThan(0);
});
