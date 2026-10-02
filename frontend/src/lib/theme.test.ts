import { readFileSync } from "node:fs";
import path from "node:path";

const css = readFileSync(path.resolve(__dirname, "../app/globals.css"), "utf8");

test("defines the SF State palette as tokens", () => {
  expect(css).toContain("--purple: #231161");
  expect(css).toContain("--gold: #b29d6c");
  expect(css).toContain("--color-purple-soft");
});

test("respects the reduced-motion preference", () => {
  expect(css).toMatch(/prefers-reduced-motion:\s*reduce/);
});
