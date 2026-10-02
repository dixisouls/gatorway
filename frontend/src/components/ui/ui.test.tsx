import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { Sparkle } from "@/components/ui/Sparkle";

test("a sheet shows its content as a labelled dialog and closes on Escape", async () => {
  const onClose = vi.fn();
  render(
    <Sheet open onClose={onClose} label="Course details">
      <p>hello</p>
    </Sheet>,
  );
  expect(screen.getByRole("dialog", { name: "Course details" })).toHaveTextContent("hello");
  await userEvent.keyboard("{Escape}");
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("clicking the backdrop closes the sheet", async () => {
  const onClose = vi.fn();
  render(
    <Sheet open onClose={onClose} label="History">
      <p>x</p>
    </Sheet>,
  );
  await userEvent.click(screen.getByTestId("sheet-backdrop"));
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("a closed sheet renders nothing and ignores Escape", async () => {
  const onClose = vi.fn();
  render(
    <Sheet open={false} onClose={onClose} label="History">
      <p>secret</p>
    </Sheet>,
  );
  expect(screen.queryByText("secret")).not.toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  expect(onClose).not.toHaveBeenCalled();
});

test("buttons forward clicks and stay quiet when disabled", async () => {
  const onClick = vi.fn();
  const { rerender } = render(<Button onClick={onClick}>Go</Button>);
  await userEvent.click(screen.getByRole("button", { name: "Go" }));
  expect(onClick).toHaveBeenCalledTimes(1);
  rerender(
    <Button onClick={onClick} disabled>
      Go
    </Button>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Go" }));
  expect(onClick).toHaveBeenCalledTimes(1);
});

test("the sparkle is decorative", () => {
  const { container } = render(<Sparkle />);
  expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
});
