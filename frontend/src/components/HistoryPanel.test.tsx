import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HistoryPanel } from "@/components/HistoryPanel";

const { listPathways } = vi.hoisted(() => ({ listPathways: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api: { listPathways } }));

const item = (id: number, interest: string | null, swaps: number) => ({
  id, program_id: 1, program_title: "BS Computer Science", roadmap_name: "R", interest, swaps, created_at: new Date().toISOString(),
});

beforeEach(() => {
  listPathways.mockReset(); // a block body: returning the mock would make Vitest call it as a teardown
});

test("lists saved roadmaps newest first and opens the one picked", async () => {
  listPathways.mockResolvedValue({ pathways: [item(2, "web development", 3), item(1, null, 0)] });
  const onPick = vi.fn();
  render(<HistoryPanel open onClose={() => {}} onPick={onPick} />);
  expect(await screen.findByText("web development")).toBeInTheDocument();
  expect(screen.getByText("Standard roadmap")).toBeInTheDocument();
  expect(screen.getByText("3 picks")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /web development/ }));
  expect(onPick).toHaveBeenCalledWith(2);
});

test("says so when nothing has been saved yet", async () => {
  listPathways.mockResolvedValue({ pathways: [] });
  render(<HistoryPanel open onClose={() => {}} onPick={() => {}} />);
  expect(await screen.findByText(/No saved roadmaps yet/)).toBeInTheDocument();
});

test("a failed load is explained", async () => {
  listPathways.mockRejectedValue(new Error("boom"));
  render(<HistoryPanel open onClose={() => {}} onPick={() => {}} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/couldn.t load your saved roadmaps/i);
});

test("does not load anything while closed", () => {
  render(<HistoryPanel open={false} onClose={() => {}} onPick={() => {}} />);
  expect(listPathways).not.toHaveBeenCalled();
});
