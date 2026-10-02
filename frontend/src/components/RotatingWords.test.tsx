import { act, renderHook } from "@testing-library/react";
import { useRotatingIndex } from "@/components/RotatingWords";

test("steps through the phrases on an interval and wraps around", () => {
  vi.useFakeTimers();
  const { result } = renderHook(() => useRotatingIndex(3, 1000));
  expect(result.current).toBe(0);
  act(() => vi.advanceTimersByTime(1000));
  expect(result.current).toBe(1);
  act(() => vi.advanceTimersByTime(2000));
  expect(result.current).toBe(0);
  vi.useRealTimers();
});

test("the words keep a real width, so a centred layout cannot collapse and clip them", async () => {
  const { render, screen } = await import("@testing-library/react");
  const { RotatingWords } = await import("@/components/RotatingWords");
  render(<RotatingWords phrases={["Reading each term"]} />);
  expect(screen.getByText("Reading each term…").parentElement).toHaveClass("w-full");
});
