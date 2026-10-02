import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InterestForm, SUGGESTIONS } from "@/components/InterestForm";

test("submits what the student typed", async () => {
  const onSubmit = vi.fn();
  render(<InterestForm onSubmit={onSubmit} />);
  await userEvent.type(screen.getByLabelText("Your interest"), "web development with Next.js{Enter}");
  expect(onSubmit).toHaveBeenCalledWith("web development with Next.js");
});

test("a suggestion fills the box", async () => {
  render(<InterestForm onSubmit={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: SUGGESTIONS[0] }));
  expect(screen.getByLabelText("Your interest")).toHaveValue(SUGGESTIONS[0]);
});

test("the build button waits for some text, and skipping needs none", async () => {
  const onSkip = vi.fn();
  render(<InterestForm onSubmit={() => {}} onSkip={onSkip} />);
  expect(screen.getByRole("button", { name: "Build my roadmap" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: /skip/i }));
  expect(onSkip).toHaveBeenCalled();
});

test("only whitespace does not count as an interest", async () => {
  render(<InterestForm onSubmit={() => {}} />);
  await userEvent.type(screen.getByLabelText("Your interest"), "   ");
  expect(screen.getByRole("button", { name: "Build my roadmap" })).toBeDisabled();
});
