import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api";
import { personalisePhrases, RoadmapView } from "@/components/RoadmapView";
import type { Pathway, SavedPathway, Slot } from "@/lib/types";
import type { RunSpec } from "@/lib/usePathwayRun";

const { baseline, createPathway, courses, options, swap, myCourses, geCourses } = vi.hoisted(() => ({
  baseline: vi.fn(), createPathway: vi.fn(), courses: vi.fn(), options: vi.fn(), swap: vi.fn(), myCourses: vi.fn(), geCourses: vi.fn(),
}));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api: { baseline, createPathway, courses, options, swap, myCourses, geCourses } }));

const slot = (over: Partial<Slot> = {}): Slot => ({
  slot_id: "a", codes: ["CSC 101"], title: "Introduction to Computing", units: 3, slot_kind: "fixed", swappable: false,
  pool_section_id: null, counts_toward_major: true, status: "planned", ...over,
});
const open = slot({ slot_id: "b", codes: [], title: "SF State Studies or University Elective", slot_kind: "free_elective", swappable: true });
const picked = slot({ slot_id: "b", codes: ["ART 101"], title: "Drawing", slot_kind: "free_elective", swappable: true, status: "replaced" });
const path = (b: Slot): Pathway => ({
  program_id: 1, program_title: "Bachelor of Science in Computer Science", program_level: "undergraduate", roadmap_id: 9,
  roadmap_name: "Bachelor of Science in Computer Science Roadmap - QR 1/2", total_units_required: 120, major_units_required: 74, unplaced_passed: [],
  terms: [{ position: 0, label: "First Semester", slots: [slot({ status: "passed" }), b] }],
});
const result = (over: Partial<SavedPathway> = {}): SavedPathway => ({
  id: 5, interest: "drawing", pathway: path(picked), applied: [{ slot_id: "b", new_course_code: "ART 101", title: "Drawing", reason: "Drawing fundamentals match your interest." }],
  dropped: [], warnings: [], intent: null, note: null, cached: false, ...over,
});
const spec = (over: Partial<RunSpec> = {}): RunSpec => ({ key: "k", programId: 1, roadmapId: 9, interest: "drawing", ...over });
const noop = () => {};

beforeEach(() => {
  [baseline, createPathway, courses, options, swap, myCourses, geCourses].forEach((m) => m.mockReset());
  localStorage.clear();
  myCourses.mockResolvedValue({ count: 0, courses: [], flagged: [] });
  geCourses.mockResolvedValue({ areas: [], courses: [] });
  baseline.mockResolvedValue({ pathway: path(open) });
  courses.mockResolvedValue({ courses: {} });
  options.mockResolvedValue({ slot_id: "b", query: "", candidates: [] });
});

test("streams the baseline in, then lets the AI picks land", async () => {
  let finish: (v: SavedPathway) => void = () => {};
  createPathway.mockReturnValue(new Promise<SavedPathway>((resolve) => (finish = resolve)));
  const s = spec();
  render(<RoadmapView spec={s} onRerun={noop} onOpenHistory={noop} />);
  expect(await screen.findByText("SF State Studies or University Elective")).toBeInTheDocument();
  expect(screen.getByText(`${personalisePhrases("drawing")[0]}…`)).toBeInTheDocument(); // words, not a bar
  finish(result());
  expect(await screen.findByText("Drawing", {}, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.getByText("Picked for you")).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByText(`${personalisePhrases("drawing")[0]}…`)).not.toBeInTheDocument());
});

test("keeps the baseline when personalising fails, and can try again", async () => {
  createPathway.mockRejectedValueOnce(new ApiError(503, "pathway_unavailable", "Pathway planning is temporarily unavailable.")).mockResolvedValueOnce(result());
  const s = spec();
  render(<RoadmapView spec={s} onRerun={noop} onOpenHistory={noop} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/temporarily unavailable/);
  expect(screen.getByText("SF State Studies or University Elective")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("Drawing", {}, { timeout: 3000 })).toBeInTheDocument();
  expect(baseline).toHaveBeenCalledTimes(2);
});

test("a roadmap that could not be built at all shows the reason", async () => {
  baseline.mockRejectedValue(new ApiError(404, "not_found", "That program has no roadmap."));
  const s = spec({ interest: null });
  render(<RoadmapView spec={s} onRerun={noop} onOpenHistory={noop} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("That program has no roadmap.");
});

test("a saved roadmap is shown straight away, picks included, without calling the server", () => {
  const s = spec({ saved: result() });
  render(<RoadmapView spec={s} onRerun={noop} onOpenHistory={noop} />);
  expect(screen.getByText("Drawing")).toBeInTheDocument();
  expect(screen.getByText("Picked for you")).toBeInTheDocument();
  expect(baseline).not.toHaveBeenCalled();
});

test("a degraded answer is explained in a soft banner", () => {
  const s = spec({ saved: result({ applied: [], pathway: path(open), note: "Personalising took too long; showing the standard roadmap." }) });
  render(<RoadmapView spec={s} onRerun={noop} onOpenHistory={noop} />);
  expect(screen.getByText(/Personalising took too long/)).toBeInTheDocument();
});

test("refresh asks again, steering away from the current picks", async () => {
  const onRerun = vi.fn();
  const s = spec({ saved: result() });
  render(<RoadmapView spec={s} onRerun={onRerun} onOpenHistory={noop} />);
  await userEvent.click(screen.getByRole("button", { name: "Refresh picks" }));
  expect(onRerun).toHaveBeenCalledWith({ programId: 1, roadmapId: 9, interest: "drawing", fresh: true, avoid: ["ART 101"] });
});

test("there is nothing to refresh without an interest", () => {
  const s = spec({ interest: null, saved: result({ interest: null, applied: [], pathway: path(open) }) });
  render(<RoadmapView spec={s} onRerun={noop} onOpenHistory={noop} />);
  expect(screen.queryByRole("button", { name: "Refresh picks" })).not.toBeInTheDocument();
});

test("a new interest re-runs the roadmap with the new text", async () => {
  const onRerun = vi.fn();
  const s = spec({ saved: result() });
  render(<RoadmapView spec={s} onRerun={onRerun} onOpenHistory={noop} />);
  await userEvent.click(screen.getByRole("button", { name: /New interest/ }));
  await userEvent.clear(screen.getByLabelText("Your interest"));
  await userEvent.type(screen.getByLabelText("Your interest"), "robotics{Enter}");
  expect(onRerun).toHaveBeenCalledWith({ programId: 1, roadmapId: 9, interest: "robotics" });
});

test("past roadmaps opens the history", async () => {
  const onOpenHistory = vi.fn();
  render(<RoadmapView spec={spec({ saved: result() })} onRerun={noop} onOpenHistory={onOpenHistory} />);
  await userEvent.click(screen.getByRole("button", { name: "Past roadmaps" }));
  expect(onOpenHistory).toHaveBeenCalled();
});

test("swapping a course in the drawer updates the card at once", async () => {
  options.mockResolvedValue({ slot_id: "b", query: "", candidates: [{ code: "CSC 667", title: "Internet Application Design", units: 3, similarity: 0.8, summary: "Web.", warnings: [] }] });
  const swapped = result({
    pathway: path(slot({ slot_id: "b", codes: ["CSC 667"], title: "Internet Application Design", slot_kind: "free_elective", swappable: true, status: "replaced" })),
    applied: [{ slot_id: "b", new_course_code: "CSC 667", title: "Internet Application Design", reason: "Your choice" }],
  });
  swap.mockResolvedValue(swapped);
  render(<RoadmapView spec={spec({ saved: result() })} onRerun={noop} onOpenHistory={noop} />);
  await userEvent.click(screen.getByRole("button", { name: /Drawing/ })); // the card expands in place
  await userEvent.click(await screen.findByRole("button", { name: "See other options" })); // then the options sheet
  await userEvent.click(await screen.findByRole("button", { name: "Use CSC 667" }));
  expect(await screen.findByText("Internet Application Design", { selector: "p" })).toBeInTheDocument();
  expect(swap).toHaveBeenCalledWith(5, "b", "CSC 667");
});

test("refresh never sends more picks to avoid than the server accepts", async () => {
  const onRerun = vi.fn();
  const many = Array.from({ length: 25 }, (_, i) => ({ slot_id: `s${i}`, new_course_code: `X ${i}`, title: "", reason: "" }));
  render(<RoadmapView spec={spec({ saved: result({ applied: many }) })} onRerun={onRerun} onOpenHistory={noop} />);
  await userEvent.click(screen.getByRole("button", { name: "Refresh picks" }));
  expect(onRerun.mock.calls[0][0].avoid).toHaveLength(20);
});

test("the working chip is valid HTML (no block inside a paragraph)", async () => {
  createPathway.mockReturnValue(new Promise(() => {})); // stays personalising
  const { container } = render(<RoadmapView spec={spec()} onRerun={noop} onOpenHistory={noop} />);
  await screen.findByText(`${personalisePhrases("drawing")[0]}…`);
  expect(container.querySelectorAll("p div, p section, p article")).toHaveLength(0);
});

test("a GE row shows the matching transcript credit and its completion is remembered", async () => {
  myCourses.mockResolvedValue({ count: 1, courses: [{ code: "GE 4", title: null, grade: "A", term: null, flagged: true }], flagged: ["GE 4"] });
  const geRow = slot({ slot_id: "g", codes: [], title: "GE Area 4: Social and Behavioral Sciences" });
  const gePath = { ...path(open), terms: [{ position: 0, label: "First Semester", slots: [geRow] }] };
  const saved = { ...result({ applied: [] }), pathway: gePath };
  const s = spec({ saved });
  const { unmount } = render(<RoadmapView spec={s} onRerun={noop} onOpenHistory={noop} />);
  expect(await screen.findByText("You have GE 4 credit on your transcript")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Mark as completed" }));
  expect(screen.getByText(/✓ Completed/)).toBeInTheDocument();
  unmount();
  render(<RoadmapView spec={s} onRerun={noop} onOpenHistory={noop} />); // reopened later
  expect(await screen.findByText(/✓ Completed/)).toBeInTheDocument();
});

test("without a transcript the roadmap says nothing is marked completed and offers to add one", async () => {
  const onAddTranscript = vi.fn();
  render(<RoadmapView spec={spec({ saved: result() })} onRerun={noop} onOpenHistory={noop} onAddTranscript={onAddTranscript} />);
  expect(await screen.findByText(/Exploring without a transcript/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Add a transcript" }));
  expect(onAddTranscript).toHaveBeenCalledTimes(1);
});

test("with a transcript on file there is no exploring notice", async () => {
  myCourses.mockResolvedValue({ count: 3, courses: [], flagged: [] });
  render(<RoadmapView spec={spec({ saved: result() })} onRerun={noop} onOpenHistory={noop} onAddTranscript={noop} />);
  await screen.findByText("Drawing");
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByText(/Exploring without a transcript/)).not.toBeInTheDocument();
});
