import { act, render, screen } from "@testing-library/react";
import { api } from "@/lib/api";
import { AuthProvider, useAuth } from "@/lib/auth";

const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function Probe() {
  const { user, ready } = useAuth();
  return <p>{user ? user.email : ready ? "signed out" : "loading"}</p>;
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

test("without a saved token the user is signed out straight away", async () => {
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  expect(await screen.findByText("signed out")).toBeInTheDocument();
});

test("a saved token is checked with the server and restores the user", async () => {
  localStorage.setItem("gatorway.token", "tok");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ id: 1, email: "a@sfsu.edu" })));
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  expect(await screen.findByText("a@sfsu.edu")).toBeInTheDocument();
});

test("a saved token the server rejects is dropped", async () => {
  localStorage.setItem("gatorway.token", "stale");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ error: { code: "unauthorized", message: "no" } }, 401)));
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  expect(await screen.findByText("signed out")).toBeInTheDocument();
  expect(localStorage.getItem("gatorway.token")).toBeNull();
});

test("a 401 anywhere signs the user out", async () => {
  localStorage.setItem("gatorway.token", "tok");
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(reply({ id: 1, email: "a@sfsu.edu" }))
    .mockResolvedValueOnce(reply({ error: { code: "unauthorized", message: "Sign in again." } }, 401));
  vi.stubGlobal("fetch", fetchMock);
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  await screen.findByText("a@sfsu.edu");
  await act(async () => {
    await api.myCourses().catch(() => {});
  });
  expect(await screen.findByText("signed out")).toBeInTheDocument();
  expect(localStorage.getItem("gatorway.token")).toBeNull();
});
