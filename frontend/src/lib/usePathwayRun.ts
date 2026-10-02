"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { Pathway, SavedPathway } from "./types";

export type Phase = "loading" | "personalising" | "done" | "error";

export interface RunSpec {
  key: string;
  programId: number;
  roadmapId: number | null;
  interest: string | null;
  fresh?: boolean;
  avoid?: string[];
  saved?: SavedPathway;
}

interface RunState {
  phase: Phase;
  baseline: Pathway | null;
  result: SavedPathway | null;
  error: string | null;
}

const LOADING: RunState = { phase: "loading", baseline: null, result: null, error: null };
const message = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

/** Draws the deterministic roadmap first, then saves the real (possibly personalised) one. `spec` must be a stable object. */
export function usePathwayRun(spec: RunSpec) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<RunState>(() =>
    spec.saved ? { phase: "done", baseline: spec.saved.pathway, result: spec.saved, error: null } : LOADING,
  );

  useEffect(() => {
    if (spec.saved) return;
    let alive = true;
    api
      .baseline(spec.programId, spec.roadmapId)
      .then(({ pathway }) => {
        if (!alive) return;
        setState((s) => ({ ...s, phase: "personalising", baseline: pathway }));
        return api
          .createPathway({ program_id: spec.programId, roadmap_id: spec.roadmapId, interest: spec.interest, fresh: spec.fresh, avoid: spec.avoid })
          .then((result) => {
            if (alive) setState((s) => ({ ...s, phase: "done", result }));
          });
      })
      .catch((e) => {
        if (alive) setState((s) => ({ ...s, phase: "error", error: message(e) }));
      });
    return () => {
      alive = false;
    };
  }, [spec, attempt]);

  const retry = useCallback(() => {
    setState(LOADING);
    setAttempt((a) => a + 1);
  }, []);
  const replaceResult = useCallback((result: SavedPathway) => setState((s) => ({ ...s, result })), []);

  return { ...state, retry, replaceResult };
}
