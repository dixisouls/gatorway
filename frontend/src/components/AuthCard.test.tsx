import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api";
import { AuthCard } from "@/components/AuthCard";

const login = vi.fn();
const signup = vi.fn();
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ login, signup }) }));

beforeEach(() => {
  login.mockReset();
  signup.mockReset();
});

async function fill(email: string, password: string) {
  await userEvent.type(screen.getByLabelText("SFSU email"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
}

test("signs in with the typed credentials", async () => {
  login.mockResolvedValue(undefined);
  render(<AuthCard />);
  await fill("a@sfsu.edu", "correct-horse-battery");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(login).toHaveBeenCalledWith("a@sfsu.edu", "correct-horse-battery");
});

test("shows the server's message when sign-in fails", async () => {
  login.mockRejectedValue(new ApiError(401, "invalid_credentials", "Invalid email or password."));
  render(<AuthCard />);
  await fill("a@sfsu.edu", "wrong-password");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled(); // can try again
});

test("switches to creating an account", async () => {
  signup.mockResolvedValue(undefined);
  render(<AuthCard />);
  await userEvent.click(screen.getByRole("button", { name: "Create an account" }));
  await fill("new@sfsu.edu", "correct-horse-battery");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(signup).toHaveBeenCalledWith("new@sfsu.edu", "correct-horse-battery");
});

test("the button is disabled while the request is running", async () => {
  let release: () => void = () => {};
  login.mockReturnValue(new Promise<void>((resolve) => (release = resolve)));
  render(<AuthCard />);
  await fill("a@sfsu.edu", "correct-horse-battery");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();
  release();
});
