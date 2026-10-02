import { act, renderHook, waitFor } from "@testing-library/react";
import { ApiError } from "@/lib/api";
import type { Pathway, SavedPathway } from "@/lib/types";
import { usePathwayRun, type RunSpec } from "@/lib/usePathwayRun";

const { baseline, createPathway } = vi.hoisted(() => ({ baseline: vi.fn(), createPathway: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api: { baseline, createPathway } }));

const pathway: Pathway = {
  program_id: 1, program_title: "BS CS", program_level: "undergraduate", roadmap_id: 9, roadmap_name: "R",
  total_units_required: 120, major_units_required: 74, terms: [], unplaced_passed: [],
};
const saved = (over: Partial<SavedPathway> = {}): SavedPathway => ({
  id: 5, interest: "web", pathway, applied: [], dropped: [], warnings: [], intent: null, note: null, cached: false, ...over,
});
const spec = (over: Partial<RunSpec> = {}): RunSpec => ({ key: "k", programId: 1, roadmapId: 9, interest: "web", ...over });

beforeEach(() => {
  baseline.mockReset();
  createPathway.mockReset();
});

test("draws the baseline first, then settles on the saved result", async () => {
  let finish: (v: SavedPathway) => void = () => {};
  baseline.mockResolvedValue({ pathway });
  createPathway.mockReturnValue(new Promise<SavedPathway>((resolve) => (finish = resolve)));
  const s = spec();
  const { result } = renderHook(() => usePathwayRun(s));
  expect(result.current.phase).toBe("loading");
  await waitFor(() => expect(result.current.phase).toBe("personalising"));
  expect(result.current.baseline).toEqual(pathway);
  expect(result.current.result).toBeNull();
  await act(async () => finish(saved()));
  expect(result.current.phase).toBe("done");
  expect(result.current.result?.id).toBe(5);
  expect(createPathway).toHaveBeenCalledWith({ program_id: 1, roadmap_id: 9, interest: "web", fresh: undefined, avoid: undefined });
});

test("keeps the baseline when personalising fails", async () => {
  baseline.mockResolvedValue({ pathway });
  createPathway.mockRejectedValue(new ApiError(503, "pathway_unavailable", "Pathway planning is temporarily unavailable."));
  const s = spec();
  const { result } = renderHook(() => usePathwayRun(s));
  await waitFor(() => expect(result.current.phase).toBe("error"));
  expect(result.current.baseline).toEqual(pathway);
  expect(result.current.error).toMatch(/temporarily unavailable/);
});

test("with no baseline at all, the error stands alone", async () => {
  baseline.mockRejectedValue(new ApiError(404, "not_found", "That program has no roadmap."));
  const s = spec();
  const { result } = renderHook(() => usePathwayRun(s));
  await waitFor(() => expect(result.current.phase).toBe("error"));
  expect(result.current.baseline).toBeNull();
  expect(createPathway).not.toHaveBeenCalled();
});

test("a saved roadmap is shown at once without calling the server", () => {
  const s = spec({ saved: saved() });
  const { result } = renderHook(() => usePathwayRun(s));
  expect(result.current.phase).toBe("done");
  expect(result.current.result?.id).toBe(5);
  expect(baseline).not.toHaveBeenCalled();
  expect(createPathway).not.toHaveBeenCalled();
});

test("retry runs the whole thing again", async () => {
  baseline.mockResolvedValue({ pathway });
  createPathway.mockRejectedValueOnce(new ApiError(503, "pathway_unavailable", "down")).mockResolvedValueOnce(saved());
  const s = spec();
  const { result } = renderHook(() => usePathwayRun(s));
  await waitFor(() => expect(result.current.phase).toBe("error"));
  act(() => result.current.retry());
  await waitFor(() => expect(result.current.phase).toBe("done"));
  expect(baseline).toHaveBeenCalledTimes(2);
});

test("a swap can replace the result in place", () => {
  const s = spec({ saved: saved() });
  const { result } = renderHook(() => usePathwayRun(s));
  act(() => result.current.replaceResult(saved({ warnings: ["changed"] })));
  expect(result.current.result?.warnings).toEqual(["changed"]);
});
