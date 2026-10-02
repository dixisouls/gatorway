import { geAreas, isGeSlot } from "@/lib/ge";
import type { Slot } from "@/lib/types";

const slot = (over: Partial<Slot>): Slot => ({
  slot_id: "s", codes: [], title: "x", units: 3, slot_kind: "fixed", swappable: false, pool_section_id: null,
  counts_toward_major: false, status: "planned", ...over,
});

test("reads the GE areas a roadmap row or a transcript line names", () => {
  expect(geAreas("GE Area 4: Social and Behavioral Sciences")).toEqual(["4"]);
  expect(geAreas("GE Area 4UD: Upper-Division Social and Behavioral Sciences")).toEqual(["4UD"]);
  expect(geAreas("GE Area 5UD or 2UD: Upper-Division Science or Math")).toEqual(["5UD", "2UD"]);
  expect(geAreas("GE Areas 5A + 5C: Physical Science and Laboratory")).toEqual(["5A", "5C"]);
  expect(geAreas("GE 4")).toEqual(["4"]);
  expect(geAreas("GE Area UD")).toEqual([]);
  expect(geAreas("Introduction to Computing")).toEqual([]);
});

test("only open rows that are about GE count as GE slots", () => {
  expect(isGeSlot(slot({ title: "GE Area 4: Social and Behavioral Sciences" }))).toBe(true);
  expect(isGeSlot(slot({ title: "GE Area 4", codes: ["SOC 100"] }))).toBe(false);
  expect(isGeSlot(slot({ title: "Select One:" }))).toBe(false);
});
