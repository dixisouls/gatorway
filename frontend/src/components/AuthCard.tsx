"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "./ui/Button";

type Mode = "login" | "signup";

export function AuthCard() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      await (mode === "login" ? login : signup)(email.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setPending(false);
    }
  }

  const label = mode === "login" ? "Sign in" : "Create account";
  const field =
    "auth-field";

  return (
    <form onSubmit={submit} className="w-full">
      <p className="eyebrow mb-3">LET’S GET YOU STARTED</p>
      <h2 className="text-[30px] font-semibold tracking-tight">{mode === "login" ? "Welcome back" : "Join GatorWay"}</h2>
      <p className="mt-3 text-sm text-muted">Use your SFSU email address.</p>
      <label className="mt-7 block text-xs font-medium text-ink">
        <span className="mb-1.5 block">SFSU email</span>
        <input className={field} type="email" autoComplete="email" placeholder="you@sfsu.edu" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label className="mt-5 block text-xs font-medium text-ink">
        <span className="mb-1.5 block">Password</span>
        <input
          className={field}
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          minLength={8}
          placeholder="At least 8 characters"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {error && (
        <p role="alert" className="mt-4 rounded-2xl bg-gold-soft px-4 py-3 text-sm text-[#6b5a2a]">
          {error}
        </p>
      )}
      <Button type="submit" className="mt-8 w-full py-3.5 text-base" disabled={pending}>
        {pending ? (mode === "login" ? "Signing in…" : "Creating account…") : label}
      </Button>
      <button
        type="button"
        className="mt-4 w-full text-center text-sm text-muted transition hover:text-purple"
        onClick={() => {
          setMode(mode === "login" ? "signup" : "login");
          setError("");
        }}
      >
        {mode === "login" ? "Create an account" : "I already have an account"}
      </button>
    </form>
  );
}
