import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api";
import { EXTRACT_PHRASES, TranscriptStep } from "@/components/TranscriptStep";

const { uploadTranscript, myCourses } = vi.hoisted(() => ({ uploadTranscript: vi.fn(), myCourses: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api: { uploadTranscript, myCourses } }));

const summary = {
  count: 2,
  courses: [
    { code: "CSC 101", grade: "A", term: "Fall 2023", flagged: false },
    { code: "ENGL 1A", title: "College Composition", grade: "A-", term: "Fall 2023", flagged: true },
  ],
  flagged: ["ENGL 1A"],
};
const pdf = () => new File(["%PDF-1.4"], "transcript.pdf", { type: "application/pdf" });
const user = () => userEvent.setup({ applyAccept: false });

beforeEach(() => {
  uploadTranscript.mockReset();
  myCourses.mockReset();
  myCourses.mockResolvedValue({ count: 0, courses: [], flagged: [] });
});

test("reads the transcript, lists the courses found and continues", async () => {
  uploadTranscript.mockResolvedValue(summary);
  const onDone = vi.fn();
  render(<TranscriptStep onDone={onDone} minMs={0} />);
  await user().upload(screen.getByLabelText("Transcript PDF"), pdf());
  expect(await screen.findByText("We found 2 courses")).toBeInTheDocument();
  const term = screen.getByRole("group", { name: "Fall 2023" }); // courses are listed under their term, not as loose chips
  expect(within(term).getByText("CSC 101")).toBeInTheDocument();
  expect(within(term).getByText("A-")).toBeInTheDocument();
  expect(within(term).getByText("College Composition")).toBeInTheDocument(); // what the transcript calls it, so the student can check it
  expect(within(term).getByText("Transfer credit")).toBeInTheDocument(); // described, not called an error
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(onDone).toHaveBeenCalled();
});

test("shows only changing words while extracting: no bar and no privacy text", async () => {
  uploadTranscript.mockReturnValue(new Promise(() => {})); // never finishes
  render(<TranscriptStep onDone={() => {}} minMs={0} />);
  await user().upload(screen.getByLabelText("Transcript PDF"), pdf());
  expect(await screen.findByText(`${EXTRACT_PHRASES[0]}…`)).toBeInTheDocument(); // the animation is up (the idle screen has left)
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.queryByText(/never stored|leaves our server|privacy/i)).not.toBeInTheDocument();
});

test("shows the server's message and lets the student try again", async () => {
  uploadTranscript.mockRejectedValue(new ApiError(422, "not_sfsu_transcript", "This does not look like an SFSU transcript. Only SFSU transcripts are supported."));
  render(<TranscriptStep onDone={() => {}} minMs={0} />);
  await user().upload(screen.getByLabelText("Transcript PDF"), pdf());
  expect(await screen.findByRole("alert")).toHaveTextContent("Only SFSU transcripts are supported.");
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(screen.getByLabelText("Transcript PDF")).toBeInTheDocument();
});

test("a network failure is explained, not a stuck spinner", async () => {
  uploadTranscript.mockRejectedValue(new ApiError(0, "network", "We can't reach the server. Check that it's running and try again."));
  render(<TranscriptStep onDone={() => {}} minMs={0} />);
  await user().upload(screen.getByLabelText("Transcript PDF"), pdf());
  expect(await screen.findByRole("alert")).toHaveTextContent(/can't reach the server/i);
});

test("a file that is not a PDF is refused before anything is sent", async () => {
  render(<TranscriptStep onDone={() => {}} minMs={0} />);
  await user().upload(screen.getByLabelText("Transcript PDF"), new File(["hi"], "notes.txt", { type: "text/plain" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/PDF/);
  expect(uploadTranscript).not.toHaveBeenCalled();
});

test("offers to reuse the courses already saved", async () => {
  myCourses.mockResolvedValue({ ...summary, count: 6 });
  const onDone = vi.fn();
  render(<TranscriptStep onDone={onDone} minMs={0} />);
  await userEvent.click(await screen.findByRole("button", { name: "Use my 6 saved courses" }));
  expect(onDone).toHaveBeenCalled();
});
