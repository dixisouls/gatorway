import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Planner } from "@/components/Planner";
import type { TranscriptSummary } from "@/lib/types";

const seen = vi.hoisted(() => ({ programStep: [] as unknown[] }));
let summary: TranscriptSummary | null = null;

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { id: 1, email: "a@sfsu.edu" }, logout: () => {} }) }));
vi.mock("@/components/TranscriptStep", () => ({
  TranscriptStep: ({ onDone, onSkip }: { onDone: (s: TranscriptSummary | null) => void; onSkip: () => void }) => (
    <div>
      <button onClick={() => onDone(summary)}>finish transcript</button>
      <button onClick={onSkip}>skip transcript</button>
    </div>
  ),
}));
vi.mock("@/components/ProgramStep", () => ({
  ProgramStep: (props: { initial?: { title: string } | null }) => {
    seen.programStep.push(props.initial ?? null);
    return <p>{props.initial ? `program step with ${props.initial.title}` : "program step: choose a degree"}</p>;
  },
}));
vi.mock("@/components/InterestStep", () => ({ InterestStep: () => <p>interest step</p> }));
vi.mock("@/components/RoadmapView", () => ({ RoadmapView: () => <p>roadmap</p> }));
vi.mock("@/components/HistoryPanel", () => ({ HistoryPanel: () => null }));
vi.mock("@/components/SetupGuide", () => ({ SetupGuide: () => null }));

const cs = { id: 605, title: "Bachelor of Science in Computer Science", slug: "cs", college: "Science", department: null, degree_type: "B.S.", level: "undergraduate", concentration: null, score: 0.97 };
const withDegree = (candidates: (typeof cs)[]): TranscriptSummary => ({ count: 1, courses: [], flagged: [], program: { raw: "B.S. Computer Science", candidates } });

beforeEach(() => {
  seen.programStep = [];
  summary = null;
});

test("a degree found on the transcript is confirmed before anything else, and yes goes straight to its roadmap options", async () => {
  summary = withDegree([cs]);
  render(<Planner />);
  await userEvent.click(screen.getByRole("button", { name: "finish transcript" }));
  expect(await screen.findByText("Is this your degree?")).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Yes, that's it" }));
  expect(await screen.findByText(`program step with ${cs.title}`)).toBeInTheDocument();
});

test("no goes to choosing the degree, as before", async () => {
  summary = withDegree([cs]);
  render(<Planner />);
  await userEvent.click(screen.getByRole("button", { name: "finish transcript" }));
  await userEvent.click(await screen.findByRole("button", { name: "No, let me choose" }));
  expect(await screen.findByText("program step: choose a degree")).toBeInTheDocument();
});

test("a transcript with no recognisable degree, or no transcript at all, goes straight to choosing", async () => {
  summary = withDegree([]);
  const first = render(<Planner />);
  await userEvent.click(screen.getByRole("button", { name: "finish transcript" }));
  expect(await screen.findByText("program step: choose a degree")).toBeInTheDocument();
  first.unmount();
  render(<Planner />);
  await userEvent.click(screen.getByRole("button", { name: "skip transcript" }));
  expect(await screen.findByText("program step: choose a degree")).toBeInTheDocument();
  expect(screen.queryByText("Is this your degree?")).not.toBeInTheDocument();
});
