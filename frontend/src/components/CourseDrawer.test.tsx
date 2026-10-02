import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api";
import { CourseDrawer } from "@/components/CourseDrawer";
import type { SavedPathway, Slot } from "@/lib/types";

const { courses, options, swap, geCourses } = vi.hoisted(() => ({ courses: vi.fn(), options: vi.fn(), swap: vi.fn(), geCourses: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api: { courses, options, swap, geCourses } }));

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
  geCourses.mockReset();
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

const geRow = () => slot({ codes: [], title: "GE Area 4: Social and Behavioral Sciences", swappable: false, slot_kind: "fixed" });
const geCourse = (code: string, title: string) => ({ code, title, units_min: 3, units_max: 3, description: `About ${title}.`, attributes: [] as string[] });

test("a GE row lists the courses that count for it, can be filtered, and can be marked completed", async () => {
  geCourses.mockResolvedValue({ areas: ["4"], courses: [geCourse("SOC 100", "Intro Sociology"), geCourse("ANTH 110", "Cultural Anthropology")] });
  const onToggle = vi.fn();
  render(<CourseDrawer slot={geRow()} pathwayId={5} canSwap onClose={noop} onSwapped={noop} ge={{ done: false, onToggle, hint: "You have GE 4 credit on your transcript" }} />);
  expect(await screen.findByText("Intro Sociology")).toBeInTheDocument();
  expect(geCourses).toHaveBeenCalledWith(["4"]);
  expect(screen.getByText("You have GE 4 credit on your transcript")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Filter courses"), "anthro");
  expect(screen.queryByText("Intro Sociology")).not.toBeInTheDocument();
  expect(screen.getByText("Cultural Anthropology")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Mark as completed" }));
  expect(onToggle).toHaveBeenCalledTimes(1);
  expect(options).not.toHaveBeenCalled(); // GE rows are not swapped, only looked up
});

test("a GE row we cannot map to an area says so instead of showing an empty list", async () => {
  render(<CourseDrawer slot={slot({ codes: [], title: "GE Area UD", swappable: false })} pathwayId={5} canSwap onClose={noop} onSwapped={noop} ge={{ done: false, onToggle: noop }} />);
  expect(await screen.findByText(/don.t have a course list for this area/i)).toBeInTheDocument();
  expect(geCourses).not.toHaveBeenCalled();
});

test("a done GE row can be undone", async () => {
  geCourses.mockResolvedValue({ areas: ["4"], courses: [] });
  const onToggle = vi.fn();
  render(<CourseDrawer slot={geRow()} pathwayId={5} canSwap onClose={noop} onSwapped={noop} ge={{ done: true, onToggle }} />);
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  expect(onToggle).toHaveBeenCalledTimes(1);
});

test("a swappable GE row offers ranked options to swap in, instead of the plain browse list", async () => {
  options.mockResolvedValue({ slot_id: "s1", query: "", candidates: [{ code: "SOC 100", title: "Intro Sociology", units: 3, similarity: 0.7, summary: "Society.", warnings: [] }] });
  swap.mockResolvedValue(result);
  const onSwapped = vi.fn();
  const row = slot({ codes: [], title: "GE Area 4: Social and Behavioral Sciences", label: "GE Area 4: Social and Behavioral Sciences", slot_kind: "ge", swappable: true });
  render(<CourseDrawer slot={row} pathwayId={5} canSwap onClose={noop} onSwapped={onSwapped} ge={{ done: false, onToggle: noop }} />);
  await userEvent.click(await screen.findByRole("button", { name: "Use SOC 100" }));
  expect(swap).toHaveBeenCalledWith(5, "s1", "SOC 100");
  await waitFor(() => expect(onSwapped).toHaveBeenCalledWith(result, "s1"));
  expect(geCourses).not.toHaveBeenCalled(); // the browse list is only for GE rows that cannot be swapped
  expect(screen.getByRole("button", { name: "Mark as completed" })).toBeInTheDocument();
});

test("a GE row that cannot be swapped yet (roadmap still building) still lets the student browse the list", async () => {
  geCourses.mockResolvedValue({ areas: ["4"], courses: [geCourse("SOC 100", "Intro Sociology")] });
  const row = slot({ codes: [], title: "GE Area 4: Social and Behavioral Sciences", label: "GE Area 4: Social and Behavioral Sciences", slot_kind: "ge", swappable: true });
  render(<CourseDrawer slot={row} pathwayId={null} canSwap={false} onClose={noop} onSwapped={noop} ge={{ done: false, onToggle: noop }} />);
  expect(await screen.findByText("Intro Sociology")).toBeInTheDocument();
  expect(options).not.toHaveBeenCalled();
});
