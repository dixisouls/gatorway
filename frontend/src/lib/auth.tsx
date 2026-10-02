"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setToken, setUnauthorizedHandler } from "./api";
import type { AuthResponse, User } from "./types";

const KEY = "gatorway.token";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const readToken = () => {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null; // storage blocked: the session just won't survive a reload
  }
};
const writeToken = (value: string | null) => {
  try {
    if (value) localStorage.setItem(KEY, value);
    else localStorage.removeItem(KEY);
  } catch {
    /* storage blocked */
  }
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const logout = useCallback(() => {
    setToken(null);
    writeToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    let alive = true;
    const saved = readToken();
    if (saved) setToken(saved);
    const session: Promise<User | null> = saved
      ? api.me().catch(() => {
          logout(); // the saved token is stale
          return null;
        })
      : Promise.resolve(null);
    session.then((u) => {
      if (!alive) return;
      if (u) setUser(u);
      setReady(true);
    });
    return () => {
      alive = false;
      setUnauthorizedHandler(null);
    };
  }, [logout]);

  const finish = useCallback((r: AuthResponse) => {
    setToken(r.access_token);
    writeToken(r.access_token);
    setUser(r.user);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      ready,
      logout,
      login: async (email, password) => finish(await api.login(email, password)),
      signup: async (email, password) => finish(await api.signup(email, password)),
    }),
    [user, ready, logout, finish],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
