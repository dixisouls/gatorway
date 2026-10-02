import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Roadmap } from "@/components/Roadmap";
import type { AppliedEdit, Pathway, Slot } from "@/lib/types";

const slot = (over: Partial<Slot> = {}): Slot => ({
  slot_id: "x", codes: ["CSC 101"], title: "Introduction to Computing", units: 3, slot_kind: "fixed", swappable: false,
  pool_section_id: null, counts_toward_major: true, status: "planned", ...over,
});
const pick = slot({ slot_id: "b", codes: ["ART 101"], title: "Drawing", slot_kind: "free_elective", swappable: true, status: "replaced" });
const was = slot({ slot_id: "b", codes: [], title: "University Elective", slot_kind: "free_elective", swappable: true });
const pathway: Pathway = {
  program_id: 1, program_title: "BS CS", program_level: "undergraduate", roadmap_id: 9, roadmap_name: "R", total_units_required: 120,
  major_units_required: 74, unplaced_passed: [],
  terms: [
    { position: 1, label: "Second Semester", slots: [slot({ slot_id: "c", codes: ["CSC 220"], title: "Data Structures", units: 4 })] },
    { position: 0, label: "First Semester", slots: [slot({ slot_id: "a", status: "passed" }), pick] },
  ],
};
const applied = new Map<string, AppliedEdit>([["b", { slot_id: "b", new_course_code: "ART 101", title: "Drawing", reason: "Fits your interest." }]]);
const props = { pathway, baselineSlots: { b: was }, applied, generating: false, onOpen: () => {} };

test("lists the terms in order, each with its units, and an arrow between terms", () => {
  render(<Roadmap {...props} isRevealed={() => true} />);
  const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
  expect(headings).toEqual(["First Semester", "Second Semester"]);
  expect(screen.getAllByText("6 units")).toHaveLength(1); // the first term's total
  expect(screen.getAllByText("4 units")).toHaveLength(2); // the second term's total and its one 4-unit card
  expect(screen.getAllByTestId("term-arrow")).toHaveLength(1);
});

test("an AI pick that has not landed yet still shows the baseline course", () => {
  render(<Roadmap {...props} isRevealed={() => false} />);
  expect(screen.getByText("University Elective")).toBeInTheDocument();
  expect(screen.queryByText("Drawing")).not.toBeInTheDocument();
});

test("once revealed the pick appears with its badge", () => {
  render(<Roadmap {...props} isRevealed={(id) => id === "b"} />);
  expect(screen.getByText("Drawing")).toBeInTheDocument();
  expect(screen.getByText("Picked for you")).toBeInTheDocument();
});

test("only electives still being decided look busy while the AI works", () => {
  const planned = slot({ slot_id: "b", codes: [], title: "University Elective", slot_kind: "free_elective", swappable: true });
  render(
    <Roadmap {...props} pathway={{ ...pathway, terms: [{ position: 0, label: "First Semester", slots: [slot({ slot_id: "a" }), planned] }] }} generating isRevealed={() => false} />,
  );
  const busy = screen.getAllByRole("button").filter((b) => b.getAttribute("aria-busy") === "true");
  expect(busy).toHaveLength(1);
  expect(within(busy[0]).getByText("University Elective")).toBeInTheDocument();
});

test("clicking a card hands its slot to the caller", async () => {
  const onOpen = vi.fn();
  render(<Roadmap {...props} onOpen={onOpen} isRevealed={() => true} />);
  await userEvent.click(screen.getByRole("button", { name: /Data Structures/ }));
  expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ slot_id: "c" }));
});
