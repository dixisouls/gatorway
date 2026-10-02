import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DegreeConfirm } from "@/components/DegreeConfirm";
import type { ProgramCandidate } from "@/lib/types";

const cand = (id: number, title: string, score: number): ProgramCandidate => ({
  id, title, slug: `p${id}`, college: "Science & Engineering", department: null, degree_type: "B.S.", level: "undergraduate", concentration: null, score,
});
const best = cand(1, "Bachelor of Science in Computer Science", 0.97);
const other = cand(2, "Minor in Computer Science", 0.6);

test("shows what the transcript says and our best match, and asks whether it is right", () => {
  render(<DegreeConfirm raw="B.S. Computer Science" candidates={[best, other]} onYes={() => {}} onNo={() => {}} />);
  expect(screen.getByText("Is this your degree?")).toBeInTheDocument();
  expect(screen.getByText(/B\.S\. Computer Science/)).toBeInTheDocument();
  expect(screen.getByText("Bachelor of Science in Computer Science")).toBeInTheDocument();
});

test("yes moves on with the best match", async () => {
  const onYes = vi.fn();
  render(<DegreeConfirm raw="B.S. Computer Science" candidates={[best, other]} onYes={onYes} onNo={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: "Yes, that's it" }));
  expect(onYes).toHaveBeenCalledWith(best);
});

test("no sends the student to choose the degree themselves", async () => {
  const onNo = vi.fn();
  render(<DegreeConfirm raw="B.S. Computer Science" candidates={[best]} onYes={() => {}} onNo={onNo} />);
  await userEvent.click(screen.getByRole("button", { name: "No, let me choose" }));
  expect(onNo).toHaveBeenCalledTimes(1);
});

test("other close matches can be picked instead", async () => {
  const onYes = vi.fn();
  render(<DegreeConfirm raw="Computer Science" candidates={[best, other]} onYes={onYes} onNo={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: "Minor in Computer Science" }));
  expect(onYes).toHaveBeenCalledWith(other);
});

test("with a single match there is no list of alternatives", () => {
  render(<DegreeConfirm raw="B.S. Computer Science" candidates={[best]} onYes={() => {}} onNo={() => {}} />);
  expect(screen.queryByText(/or did you mean/i)).not.toBeInTheDocument();
});
