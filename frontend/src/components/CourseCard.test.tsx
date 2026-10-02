import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CourseCard } from "@/components/CourseCard";
import type { Slot } from "@/lib/types";

const { courses } = vi.hoisted(() => ({ courses: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api: { courses } }));

const slot = (over: Partial<Slot> = {}): Slot => ({
  slot_id: "s1", codes: ["CSC 220"], title: "Data Structures", units: 3, slot_kind: "fixed", swappable: false,
  pool_section_id: null, counts_toward_major: true, status: "planned", ...over,
});
const base = { isPick: false, generating: false, enterDelay: 0, onOpen: () => {} };
const detail = { code: "CSC 220", title: "Data Structures", units_min: 3, units_max: 3, description: "Lists, trees and graphs.", prereq_text: "Prerequisite: CSC 215.", prereq_groups: [], attributes: ["Writing intensive"] };

beforeEach(() => {
  courses.mockReset();
  courses.mockResolvedValue({ courses: { "CSC 220": detail } });
});

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

test("a card expands in place to show what the course is about, and collapses again", async () => {
  render(<CourseCard slot={slot()} {...base} />);
  const header = screen.getByRole("button", { name: /Data Structures/ });
  expect(header).toHaveAttribute("aria-expanded", "false");
  await userEvent.click(header);
  expect(header).toHaveAttribute("aria-expanded", "true");
  expect(await screen.findByText("Lists, trees and graphs.")).toBeInTheDocument();
  expect(screen.getByText("Prerequisite: CSC 215.")).toBeInTheDocument();
  expect(screen.getByText("Writing intensive")).toBeInTheDocument();
  expect(courses).toHaveBeenCalledTimes(1);
  await userEvent.click(header);
  expect(header).toHaveAttribute("aria-expanded", "false");
});

test("an expanded elective offers the other options", async () => {
  const onOpen = vi.fn();
  render(<CourseCard slot={slot({ swappable: true, slot_kind: "free_elective" })} {...base} onOpen={onOpen} />);
  await userEvent.click(screen.getByRole("button", { name: /Data Structures/ }));
  await userEvent.click(await screen.findByRole("button", { name: "See other options" }));
  expect(onOpen).toHaveBeenCalledTimes(1);
});

test("a fixed course offers no options", async () => {
  render(<CourseCard slot={slot()} {...base} />);
  await userEvent.click(screen.getByRole("button", { name: /Data Structures/ }));
  await screen.findByText("Lists, trees and graphs.");
  expect(screen.queryByRole("button", { name: "See other options" })).not.toBeInTheDocument();
});

test("an open elective slot has nothing to expand: clicking goes straight to the options", async () => {
  const onOpen = vi.fn();
  render(<CourseCard slot={slot({ codes: [], title: "Major Elective (6 Units Total)", slot_kind: "major_elective", swappable: true })} {...base} onOpen={onOpen} />);
  expect(screen.getByText("Major elective")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Major Elective/ }));
  expect(onOpen).toHaveBeenCalledTimes(1);
  expect(courses).not.toHaveBeenCalled();
});

test("a card the AI is still working on is marked busy", () => {
  render(<CourseCard slot={slot({ codes: [], swappable: true, slot_kind: "free_elective" })} {...base} generating />);
  expect(screen.getByRole("button", { name: /Data Structures/ }).closest("article")).toHaveAttribute("aria-busy", "true");
});

test("a plain requirement row with nothing to show is not clickable", () => {
  render(<CourseCard slot={slot({ codes: [], title: "GE Area 4", swappable: false })} {...base} />);
  expect(screen.getByRole("button", { name: /GE Area 4/ })).toBeDisabled();
});
