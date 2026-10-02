import { act, render, screen } from "@testing-library/react";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { AuthProvider, friendlyAuthError, useAuth } from "@/lib/auth";

const fb = vi.hoisted(() => ({
  listener: null as null | ((u: unknown) => void),
  authObj: { currentUser: null as null | { getIdToken: () => Promise<string> } },
  signIn: vi.fn(),
  createUser: vi.fn(),
  signOut: vi.fn(),
  configured: true,
}));
vi.mock("@/lib/firebase", () => ({
  firebaseAuth: () => {
    if (!fb.configured) throw new Error("Firebase is not configured. Set NEXT_PUBLIC_FIREBASE_* in .env.");
    return fb.authObj;
  },
}));
vi.mock("firebase/auth", () => ({
  onAuthStateChanged: (_auth: unknown, cb: (u: unknown) => void) => {
    fb.listener = cb;
    return () => {};
  },
  signInWithEmailAndPassword: fb.signIn,
  createUserWithEmailAndPassword: fb.createUser,
  signOut: fb.signOut,
}));

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const ME = { id: 1, email: "a@sfsu.edu" };
let ctx: ReturnType<typeof useAuth>;

function Probe() {
  const auth = useAuth();
  useEffect(() => {
    ctx = auth; // tests call login/signup/logout through this
  });
  return <p>{auth.user ? auth.user.email : auth.ready ? "signed out" : "loading"}</p>;
}
const mount = () =>
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
const firebaseSays = (user: unknown) => act(async () => fb.listener?.(user));

beforeEach(() => {
  fb.listener = null;
  fb.configured = true;
  fb.authObj.currentUser = { getIdToken: async () => "id-token" };
  fb.signIn.mockReset().mockResolvedValue({});
  fb.createUser.mockReset().mockResolvedValue({});
  fb.signOut.mockReset().mockResolvedValue(undefined);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(ME)));
});
afterEach(() => vi.unstubAllGlobals());

test("with no Firebase user the student is signed out", async () => {
  mount();
  await firebaseSays(null);
  expect(await screen.findByText("signed out")).toBeInTheDocument();
});

test("a Firebase user is confirmed with the backend, which creates their local record", async () => {
  mount();
  await firebaseSays({ uid: "u1" });
  expect(await screen.findByText("a@sfsu.edu")).toBeInTheDocument();
  const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(String(url)).toMatch(/\/auth\/me$/);
  expect(init.headers.Authorization).toBe("Bearer id-token"); // the live Firebase ID token, fetched fresh
});

test("a Firebase user the backend refuses (not an SFSU address) is signed straight out again", async () => {
  (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(reply({ error: { code: "invalid_email", message: "Use your SFSU email address." } }, 403));
  mount();
  await firebaseSays({ uid: "u1" });
  expect(await screen.findByText("signed out")).toBeInTheDocument();
  expect(fb.signOut).toHaveBeenCalled();
});

test("a 401 anywhere signs the user out", async () => {
  mount();
  await firebaseSays({ uid: "u1" });
  await screen.findByText("a@sfsu.edu");
  (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(reply({ error: { code: "invalid_token", message: "Sign in again." } }, 401));
  await act(async () => {
    await api.myCourses().catch(() => {});
  });
  expect(fb.signOut).toHaveBeenCalled();
});

test("signing in goes through Firebase and then the backend", async () => {
  mount();
  await firebaseSays(null);
  await act(async () => ctx.login("  a@sfsu.edu ", "correct-horse-battery"));
  expect(fb.signIn).toHaveBeenCalledWith(fb.authObj, "a@sfsu.edu", "correct-horse-battery");
});

test("a wrong password is reported in plain words", async () => {
  fb.signIn.mockRejectedValue({ code: "auth/invalid-credential" });
  mount();
  await firebaseSays(null);
  await expect(ctx.login("a@sfsu.edu", "wrong-password")).rejects.toThrow("Invalid email or password.");
});

test("creating an account creates it in Firebase", async () => {
  mount();
  await firebaseSays(null);
  await act(async () => ctx.signup("new@mail.sfsu.edu", "correct-horse-battery"));
  expect(fb.createUser).toHaveBeenCalledWith(fb.authObj, "new@mail.sfsu.edu", "correct-horse-battery");
});

test("a non-SFSU address is turned away before anything is created in Firebase", async () => {
  mount();
  await firebaseSays(null);
  await expect(ctx.signup("someone@gmail.com", "correct-horse-battery")).rejects.toThrow(/SFSU email/);
  expect(fb.createUser).not.toHaveBeenCalled();
});

test("an address that is already registered says so", async () => {
  fb.createUser.mockRejectedValue({ code: "auth/email-already-in-use" });
  mount();
  await firebaseSays(null);
  await expect(ctx.signup("a@sfsu.edu", "correct-horse-battery")).rejects.toThrow(/already exists/);
});

test("signing out signs out of Firebase", async () => {
  mount();
  await firebaseSays({ uid: "u1" });
  await screen.findByText("a@sfsu.edu");
  act(() => ctx.logout());
  expect(fb.signOut).toHaveBeenCalled();
});

test("Firebase error codes become friendly messages", () => {
  expect(friendlyAuthError({ code: "auth/weak-password" })).toMatch(/stronger password/);
  expect(friendlyAuthError({ code: "auth/too-many-requests" })).toMatch(/Too many attempts/);
  expect(friendlyAuthError({ code: "auth/network-request-failed" })).toMatch(/can't reach/i);
  expect(friendlyAuthError(new Error("Firebase is not configured."))).toBe("Firebase is not configured.");
  expect(friendlyAuthError("???")).toMatch(/Something went wrong/);
});

test("without Firebase configured the student is simply signed out, and sign-in explains why", async () => {
  fb.configured = false;
  mount();
  expect(await screen.findByText("signed out")).toBeInTheDocument();
  await expect(ctx.login("a@sfsu.edu", "correct-horse-battery")).rejects.toThrow(/Firebase is not configured/);
});
