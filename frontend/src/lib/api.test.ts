import { api, ApiError, setToken, setUnauthorizedHandler } from "@/lib/api";

const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => {
  vi.unstubAllGlobals();
  setToken(null);
  setUnauthorizedHandler(null);
});

test("sends the bearer token and a JSON body", async () => {
  const fetchMock = vi.fn().mockResolvedValue(reply({ pathway: {} }));
  vi.stubGlobal("fetch", fetchMock);
  setToken("tok");
  await api.baseline(5, null);
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toMatch(/\/pathways\/baseline$/);
  expect(init.headers.Authorization).toBe("Bearer tok");
  expect(init.headers["Content-Type"]).toBe("application/json");
  expect(JSON.parse(init.body)).toEqual({ program_id: 5, roadmap_id: null });
});

test("turns the error envelope into an ApiError the UI can show", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ error: { code: "not_sfsu_transcript", message: "Only SFSU transcripts.", details: null } }, 422)));
  const err = await api.myCourses().catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err).toMatchObject({ status: 422, code: "not_sfsu_transcript", message: "Only SFSU transcripts." });
});

test("a dropped connection becomes a friendly network error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  const err = await api.me().catch((e) => e);
  expect(err).toMatchObject({ status: 0, code: "network" });
  expect(err.message).toMatch(/can't reach the server/i);
});

test("a 401 while signed in calls the unauthorized handler", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ error: { code: "unauthorized", message: "Sign in again." } }, 401)));
  const handler = vi.fn();
  setUnauthorizedHandler(handler);
  setToken("tok");
  await api.myCourses().catch(() => {});
  expect(handler).toHaveBeenCalledTimes(1);
});

test("a wrong password at sign-in does not look like an expired session", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ error: { code: "invalid_credentials", message: "Invalid email or password." } }, 401)));
  const handler = vi.fn();
  setUnauthorizedHandler(handler);
  setToken("old");
  await api.login("a@sfsu.edu", "wrong-password").catch(() => {});
  expect(handler).not.toHaveBeenCalled();
});

test("uploads the transcript as multipart without forcing a JSON content type", async () => {
  const fetchMock = vi.fn().mockResolvedValue(reply({ count: 0, courses: [], flagged: [] }, 201));
  vi.stubGlobal("fetch", fetchMock);
  await api.uploadTranscript(new File(["%PDF"], "t.pdf", { type: "application/pdf" }));
  const [, init] = fetchMock.mock.calls[0];
  expect(init.body).toBeInstanceOf(FormData);
  expect(init.headers["Content-Type"]).toBeUndefined();
});

test("builds query strings and skips empty values", async () => {
  const fetchMock = vi.fn().mockResolvedValue(reply({ programs: [] }));
  vi.stubGlobal("fetch", fetchMock);
  await api.programs("", "undergraduate");
  const url = String(fetchMock.mock.calls[0][0]);
  expect(url).toContain("level=undergraduate");
  expect(url).toContain("limit=12");
  expect(url).not.toContain("query=");
});

test("encodes slot ids and course codes in URLs", async () => {
  const fetchMock = vi.fn().mockResolvedValue(reply({ slot_id: "a/b", query: "", candidates: [] }));
  vi.stubGlobal("fetch", fetchMock);
  await api.options(3, "a/b", "web apps");
  expect(String(fetchMock.mock.calls[0][0])).toContain("/pathways/3/slots/a%2Fb/options?query=web+apps");
  await api.courses(["CSC 101", "MATH 226"]);
  expect(String(fetchMock.mock.calls[1][0])).toContain("codes=CSC+101%2CMATH+226");
});
