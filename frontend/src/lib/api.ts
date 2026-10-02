import type {
  CourseDetail, OptionsResponse, Pathway, PathwayListItem, ProgramBrief, RoadmapBrief, SavedPathway,
  TranscriptSummary, User, GeCourse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let tokenProvider: (() => Promise<string | null>) | null = null;
let onUnauthorized: (() => void) | null = null;
/** Firebase ID tokens expire hourly, so every request asks for the current one instead of holding a string. */
export const setTokenProvider = (fn: (() => Promise<string | null>) | null) => {
  tokenProvider = fn;
};
export const setUnauthorizedHandler = (fn: (() => void) | null) => {
  onUnauthorized = fn;
};

interface Init {
  method?: string;
  json?: unknown;
  form?: FormData;
}

async function request<T>(path: string, init: Init = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = (await tokenProvider?.().catch(() => null)) ?? null;
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  } else if (init.form) {
    body = init.form; // the browser sets the multipart boundary itself
  }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { method: init.method ?? "GET", headers, body });
  } catch {
    throw new ApiError(0, "network", "We can't reach the server. Check that it's running and try again.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error ?? {};
    if (res.status === 401 && token) onUnauthorized?.();
    throw new ApiError(res.status, err.code ?? "error", err.message ?? "Something went wrong. Please try again.", err.details);
  }
  return data as T;
}

const query = (params: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") s.set(k, String(v));
  const text = s.toString();
  return text ? `?${text}` : "";
};

export const api = {
  me: () => request<User>("/auth/me"),
  uploadTranscript: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<TranscriptSummary>("/transcripts", { method: "POST", form });
  },
  myCourses: () => request<TranscriptSummary>("/me/courses"),
  programs: (q: string, level: string) => request<{ programs: ProgramBrief[] }>(`/programs${query({ query: q, level, limit: 12 })}`),
  roadmaps: (programId: number) => request<{ roadmaps: RoadmapBrief[] }>(`/programs/${programId}/roadmaps`),
  baseline: (programId: number, roadmapId: number | null) =>
    request<{ pathway: Pathway }>("/pathways/baseline", { method: "POST", json: { program_id: programId, roadmap_id: roadmapId } }),
  createPathway: (body: { program_id: number; roadmap_id?: number | null; interest?: string | null; fresh?: boolean; avoid?: string[] }) =>
    request<SavedPathway>("/pathways", { method: "POST", json: body }),
  listPathways: () => request<{ pathways: PathwayListItem[] }>("/pathways"),
  getPathway: (id: number) => request<SavedPathway>(`/pathways/${id}`),
  options: (id: number, slotId: string, q: string, limit = 8) =>
    request<OptionsResponse>(`/pathways/${id}/slots/${encodeURIComponent(slotId)}/options${query({ query: q, limit })}`),
  swap: (id: number, slotId: string, code: string) =>
    request<SavedPathway>(`/pathways/${id}/swap`, { method: "POST", json: { slot_id: slotId, new_course_code: code } }),
  geCourses: (areas: string[]) => request<{ areas: string[]; courses: GeCourse[] }>(`/courses/ge${query({ areas: areas.join(",") })}`),
  courses: (codes: string[]) => request<{ courses: Record<string, CourseDetail> }>(`/courses${query({ codes: codes.join(",") })}`),
};
