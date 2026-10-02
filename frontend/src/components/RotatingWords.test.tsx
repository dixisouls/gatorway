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
