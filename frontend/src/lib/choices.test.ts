import { readChoices, writeChoices } from "@/lib/choices";

afterEach(() => localStorage.clear());

test("choices are remembered per roadmap", () => {
  writeChoices("k1", { h: "CHEM 115" });
  expect(readChoices("k1")).toEqual({ h: "CHEM 115" });
  expect(readChoices("k2")).toEqual({});
});

test("unreadable or broken storage never throws", () => {
  localStorage.setItem("k3", "{not json");
  expect(readChoices("k3")).toEqual({});
});
