import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api";
import { CourseDrawer } from "@/components/CourseDrawer";
import type { SavedPathway, Slot } from "@/lib/types";

const { courses, options, swap } = vi.hoisted(() => ({ courses: vi.fn(), options: vi.fn(), swap: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api: { courses, options, swap } }));

const slot = (over: Partial<Slot> = {}): Slot => ({
  slot_id: "s1", codes: [], title: "University Elective", units: 3, slot_kind: "free_elective", swappable: true,
  pool_section_id: null, counts_toward_major: false, status: "planned", ...over,
});
const candidate = (code: string, title: string, similarity = 0.8) => ({ code, title, units: 3, similarity, summary: `About ${title}.`, warnings: [] as string[] });
const result = { id: 5 } as SavedPathway;
const noop = () => {};

beforeEach(() => {
  courses.mockReset();
  options.mockReset();
  swap.mockReset();
  courses.mockResolvedValue({ courses: {} });
  options.mockResolvedValue({ slot_id: "s1", query: "", candidates: [candidate("CSC 667", "Internet Application Design"), candidate("CSC 675", "Database Systems", 0.6)] });
});

test("shows what a course is about, its prerequisites and attributes", async () => {
  courses.mockResolvedValue({
    courses: {
      "CSC 220": { code: "CSC 220", title: "Data Structures", units_min: 3, units_max: 3, description: "Lists, trees and graphs.", prereq_text: "Prerequisite: CSC 215.", prereq_groups: [["CSC 215"]], attributes: ["Writing intensive"] },
    },
  });
  render(<CourseDrawer slot={slot({ codes: ["CSC 220"], title: "Data Structures", swappable: false, slot_kind: "fixed" })} pathwayId={5} canSwap onClose={noop} onSwapped={noop} />);
  expect(await screen.findByText("Lists, trees and graphs.")).toBeInTheDocument();
  expect(screen.getByText("Prerequisite: CSC 215.")).toBeInTheDocument();
  expect(screen.getByText("Writing intensive")).toBeInTheDocument();
  expect(options).not.toHaveBeenCalled(); // a fixed course has no alternatives
});

test("says why the AI picked a course", async () => {
  render(
    <CourseDrawer
      slot={slot({ codes: ["ART 101"], title: "Drawing", status: "replaced" })}
      applied={{ slot_id: "s1", new_course_code: "ART 101", title: "Drawing", reason: "Drawing fundamentals match your interest." }}
      pathwayId={5} canSwap onClose={noop} onSwapped={noop}
    />,
  );
  expect(await screen.findByText("Drawing fundamentals match your interest.")).toBeInTheDocument();
  expect(screen.getByText("Why this was picked")).toBeInTheDocument();
});

test("a completed course says so and offers no swap", async () => {
  render(<CourseDrawer slot={slot({ codes: ["CSC 101"], title: "Intro", status: "passed", swappable: false, slot_kind: "fixed" })} pathwayId={5} canSwap onClose={noop} onSwapped={noop} />);
  expect(await screen.findByText(/You.ve completed this course/)).toBeInTheDocument();
  expect(options).not.toHaveBeenCalled();
});

test("lists the options for a swappable slot and swaps on request", async () => {
  swap.mockResolvedValue(result);
  const onSwapped = vi.fn();
  render(<CourseDrawer slot={slot()} pathwayId={5} canSwap onClose={noop} onSwapped={onSwapped} />);
  expect(await screen.findByText("Internet Application Design")).toBeInTheDocument();
  expect(screen.getByText("Database Systems")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Use CSC 667" }));
  expect(swap).toHaveBeenCalledWith(5, "s1", "CSC 667");
  await waitFor(() => expect(onSwapped).toHaveBeenCalledWith(result, "s1"));
});

test("a swap the validator refuses is explained and can be retried", async () => {
  swap.mockRejectedValue(new ApiError(422, "swap_rejected", "CSC 667 is already passed or planned"));
  const onSwapped = vi.fn();
  render(<CourseDrawer slot={slot()} pathwayId={5} canSwap onClose={noop} onSwapped={onSwapped} />);
  await userEvent.click(await screen.findByRole("button", { name: "Use CSC 667" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already passed or planned");
  expect(onSwapped).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Use CSC 667" })).toBeEnabled();
});

test("searching changes the options", async () => {
  render(<CourseDrawer slot={slot()} pathwayId={5} canSwap onClose={noop} onSwapped={noop} />);
  await screen.findByText("Internet Application Design");
  await userEvent.type(screen.getByLabelText("Search options"), "databases");
  await waitFor(() => expect(options).toHaveBeenLastCalledWith(5, "s1", "databases"));
});

test("says so when nothing else fits", async () => {
  options.mockResolvedValue({ slot_id: "s1", query: "", candidates: [] });
  render(<CourseDrawer slot={slot()} pathwayId={5} canSwap onClose={noop} onSwapped={noop} />);
  expect(await screen.findByText(/No other courses fit this slot right now/)).toBeInTheDocument();
});

test("options that cannot load are explained", async () => {
  options.mockRejectedValue(new ApiError(503, "pathway_unavailable", "Pathway planning is temporarily unavailable."));
  render(<CourseDrawer slot={slot()} pathwayId={5} canSwap onClose={noop} onSwapped={noop} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("temporarily unavailable");
});

test("no options are requested while the roadmap is still being built", async () => {
  render(<CourseDrawer slot={slot()} pathwayId={null} canSwap={false} onClose={noop} onSwapped={noop} />);
  expect(await screen.findByText(/Course options unlock when your roadmap has finished building/)).toBeInTheDocument();
  expect(options).not.toHaveBeenCalled();
});

test("closed when there is no slot", () => {
  render(<CourseDrawer slot={null} pathwayId={5} canSwap onClose={noop} onSwapped={noop} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
