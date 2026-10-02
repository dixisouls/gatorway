"use client";

import { Landing } from "@/components/Landing";
import { Planner } from "@/components/Planner";
import { Sparkle } from "@/components/ui/Sparkle";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <main className="grid min-h-dvh place-items-center">
        <Sparkle size={36} spin />
      </main>
    );
  }
  return user ? <Planner /> : <Landing />;
}
