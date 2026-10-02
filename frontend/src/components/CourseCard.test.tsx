import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CourseCard } from "@/components/CourseCard";
import type { Slot } from "@/lib/types";

const slot = (over: Partial<Slot> = {}): Slot => ({
  slot_id: "s1", codes: ["CSC 220"], title: "Data Structures", units: 3, slot_kind: "fixed", swappable: false,
  pool_section_id: null, counts_toward_major: true, status: "planned", ...over,
});
const base = { isPick: false, generating: false, enterDelay: 0, onOpen: () => {} };

test("shows the code, title and units", () => {
  render(<CourseCard slot={slot()} {...base} />);
  expect(screen.getByText("CSC 220")).toBeInTheDocument();
  expect(screen.getByText("Data Structures")).toBeInTheDocument();
  expect(screen.getByText("3 units")).toBeInTheDocument();
});

test("a lecture and lab read as one course line", () => {
  render(<CourseCard slot={slot({ codes: ["PHYS 220", "PHYS 222"], units: 4 })} {...base} />);
  expect(screen.getByText("PHYS 220 + PHYS 222")).toBeInTheDocument();
});

test("a completed course says so", () => {
  render(<CourseCard slot={slot({ status: "passed" })} {...base} />);
  expect(screen.getByText(/Completed/)).toBeInTheDocument();
});

test("an AI pick wears the sparkle badge and says why", () => {
  render(
    <CourseCard
      slot={slot({ codes: ["ART 101"], title: "Drawing", status: "replaced", swappable: true, slot_kind: "free_elective" })}
      applied={{ slot_id: "s1", new_course_code: "ART 101", title: "Drawing", reason: "Drawing fundamentals match your interest." }}
      {...base}
      isPick
    />,
  );
  expect(screen.getByText("Picked for you")).toBeInTheDocument();
  expect(screen.getByText("Drawing fundamentals match your interest.")).toBeInTheDocument();
});

test("an open elective slot shows its kind and invites a look at the options", () => {
  render(<CourseCard slot={slot({ codes: [], title: "Major Elective (6 Units Total)", slot_kind: "major_elective", swappable: true })} {...base} />);
  expect(screen.getByText("Major elective")).toBeInTheDocument();
  expect(screen.getByText(/See options/)).toBeInTheDocument();
});

test("a card the AI is still working on is marked busy", () => {
  render(<CourseCard slot={slot({ codes: [], swappable: true, slot_kind: "free_elective" })} {...base} generating />);
  expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true");
});

test("clicking opens the details; a plain requirement row with nothing to show is not clickable", async () => {
  const onOpen = vi.fn();
  const { rerender } = render(<CourseCard slot={slot()} {...base} onOpen={onOpen} />);
  await userEvent.click(screen.getByRole("button"));
  expect(onOpen).toHaveBeenCalledTimes(1);
  rerender(<CourseCard slot={slot({ codes: [], title: "GE Area 4", swappable: false })} {...base} onOpen={onOpen} />);
  expect(screen.getByRole("button")).toBeDisabled();
});
