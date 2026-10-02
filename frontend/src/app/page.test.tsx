import { render, screen } from "@testing-library/react";
import Home from "@/app/page";

const auth = vi.hoisted(() => ({ value: { user: null as null | { id: number; email: string }, ready: false } }));
vi.mock("@/lib/auth", () => ({ useAuth: () => auth.value }));
vi.mock("@/components/Planner", () => ({ Planner: () => <p>planner</p> }));
vi.mock("@/components/Landing", () => ({ Landing: () => <p>landing</p> }));

test("shows nothing but a splash until the session is checked", () => {
  auth.value = { user: null, ready: false };
  render(<Home />);
  expect(screen.queryByText("landing")).not.toBeInTheDocument();
  expect(screen.queryByText("planner")).not.toBeInTheDocument();
});

test("signed-out visitors see the landing page", () => {
  auth.value = { user: null, ready: true };
  render(<Home />);
  expect(screen.getByText("landing")).toBeInTheDocument();
});

test("signed-in students go straight to the planner", () => {
  auth.value = { user: { id: 1, email: "a@sfsu.edu" }, ready: true };
  render(<Home />);
  expect(screen.getByText("planner")).toBeInTheDocument();
});
