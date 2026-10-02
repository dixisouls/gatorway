import { groupChoices } from "@/lib/groups";
import type { Slot } from "@/lib/types";

const slot = (id: string, over: Partial<Slot> = {}): Slot => ({
  slot_id: id, codes: [id], title: id, units: 3, slot_kind: "fixed", swappable: false, pool_section_id: null,
  counts_toward_major: true, status: "planned", ...over,
});
const header = (id = "h", title = "Select One (Major Core):") => slot(id, { codes: [], title, units: 4 });
const alt = (id: string, over: Partial<Slot> = {}) => slot(id, { units: 0, ...over });

test("a Select One row and the zero-unit alternatives after it become one choice", () => {
  const items = groupChoices([slot("a"), header(), alt("c1"), alt("c2"), slot("b")]);
  expect(items.map((i) => i.kind)).toEqual(["slot", "choice", "slot"]);
  const choice = items[1];
  expect(choice.kind === "choice" && choice.options.map((o) => o.slot_id)).toEqual(["c1", "c2"]);
});

test("normal courses with units are never swallowed into a choice", () => {
  const items = groupChoices([header(), alt("c1"), alt("c2"), slot("real")]);
  expect(items.map((i) => i.kind)).toEqual(["choice", "slot"]);
});

test("a Select One row with fewer than two alternatives stays as ordinary rows", () => {
  const items = groupChoices([header(), alt("c1"), slot("b")]);
  expect(items.map((i) => i.kind)).toEqual(["slot", "slot", "slot"]);
});

test("only rows that say Select are headers; an open GE row is not", () => {
  const ge = slot("ge", { codes: [], title: "GE Area 4: Social and Behavioral Sciences" });
  expect(groupChoices([ge, alt("c1"), alt("c2")]).map((i) => i.kind)).toEqual(["slot", "slot", "slot"]);
});
