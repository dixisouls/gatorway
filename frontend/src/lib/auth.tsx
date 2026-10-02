"use client";

import { type Auth, createUserWithEmailAndPassword, onAuthStateChanged, signInWithEmailAndPassword, signOut } from "firebase/auth";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError, setTokenProvider, setUnauthorizedHandler } from "./api";
import { firebaseAuth } from "./firebase";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const SFSU_EMAIL = /^[^@\s]+@([a-z0-9-]+\.)*sfsu\.edu$/i;

/** Firebase error codes (and our own API errors) in plain words. */
export function friendlyAuthError(e: unknown): string {
  switch ((e as { code?: string } | null)?.code) {
    case "auth/invalid-credential":
    case "auth/invalid-login-credentials":
    case "auth/user-not-found":
    case "auth/wrong-password":
      return "Invalid email or password.";
    case "auth/email-already-in-use":
      return "An account with this email already exists. Try signing in.";
    case "auth/weak-password":
      return "Choose a stronger password (at least 6 characters).";
    case "auth/invalid-email":
      return "That email address doesn't look right.";
    case "auth/too-many-requests":
      return "Too many attempts. Please wait a moment and try again.";
    case "auth/network-request-failed":
      return "We can't reach the sign-in service. Check your connection and try again.";
  }
  if (e instanceof ApiError || (e instanceof Error && e.message)) return (e as Error).message;
  return "Something went wrong. Please try again.";
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let auth: Auth;
    try {
      auth = firebaseAuth();
    } catch {
      void Promise.resolve().then(() => setReady(true)); // not configured: signed out; signing in explains what is missing
      return;
    }
    setTokenProvider(async () => (await auth.currentUser?.getIdToken()) ?? null);
    setUnauthorizedHandler(() => void signOut(auth));
    let alive = true;
    const stop = onAuthStateChanged(auth, async (fbUser) => {
      if (!fbUser) {
        if (alive) {
          setUser(null);
          setReady(true);
        }
        return;
      }
      try {
        const me = await api.me(); // also creates the student's local record on first sign-in
        if (alive) setUser(me);
      } catch {
        await signOut(auth).catch(() => {}); // the backend refused this account (not an SFSU address, or an invalid session)
        if (alive) setUser(null);
      }
      if (alive) setReady(true);
    });
    return () => {
      alive = false;
      stop();
      setTokenProvider(null);
      setUnauthorizedHandler(null);
    };
  }, []);

  const logout = useCallback(() => {
    try {
      void signOut(firebaseAuth());
    } catch {
      /* not configured: nothing to sign out of */
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      ready,
      logout,
      login: async (email, password) => {
        try {
          const auth = firebaseAuth();
          await signInWithEmailAndPassword(auth, email.trim(), password);
          await api.me();
        } catch (e) {
          await signOut(firebaseAuth()).catch(() => {});
          throw new Error(friendlyAuthError(e));
        }
      },
      signup: async (email, password) => {
        if (!SFSU_EMAIL.test(email.trim())) throw new Error("Use your SFSU email address (it must end in sfsu.edu).");
        try {
          const auth = firebaseAuth();
          await createUserWithEmailAndPassword(auth, email.trim(), password);
          await api.me();
        } catch (e) {
          await signOut(firebaseAuth()).catch(() => {});
          throw new Error(friendlyAuthError(e));
        }
      },
    }),
    [user, ready, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
