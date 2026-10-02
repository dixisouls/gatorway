"use client";

import { motion } from "motion/react";
import { AuthCard } from "./AuthCard";
import { Brand } from "./ui/Brand";
import { Sparkle } from "./ui/Sparkle";

export function Landing() {
  return (
    <div className="site-shell">
      <header className="site-header"><Brand /><span className="campus-tag"><span /> Made for SF State</span></header>
      <main className="welcome-layout">
        <motion.section className="welcome-story" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }}>
          <span className="welcome-badge"><Sparkle size={14} /> A little clarity for what’s next</span>
          <h1>Big ambitions.<br /><span>A plan to get there.</span></h1>
          <p className="welcome-description">Connect what you’ve learned with what you love. Build a path through college that feels like yours.</p>
          <div className="path-preview" aria-label="How your plan comes together">
            <div className="preview-topline"><span>YOUR WAY FORWARD</span><span className="preview-label">The big picture ↗</span></div>
            <div className="preview-stop"><span className="preview-symbol complete">✓</span><div><small>START WITH YOUR PROGRESS</small><strong>The credit you’ve earned</strong></div><span className="preview-pill">Your transcript</span></div>
            <div className="preview-stop"><span className="preview-symbol current">↗</span><div><small>FIND YOUR DIRECTION</small><strong>The degree you’re working toward</strong></div></div>
            <div className="preview-stop"><span className="preview-symbol future">✦</span><div><small>MAKE IT PERSONAL</small><strong>Electives that spark something</strong></div><Sparkle size={18} /></div>
            <div className="preview-bottom"><span className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-[#c4b5fd]" /> One semester at a time</span><span>→</span></div>
          </div>
          <p className="welcome-footnote">Your progress + your interests. Finally, in the same plan.</p>
        </motion.section>
        <section className="welcome-auth" aria-label="Get started">
          <AuthCard />
          <div className="auth-context"><span className="auth-context-icon">↗</span><p>Your next chapter, organized.<br /><span>Upload. Explore. Make it yours.</span></p></div>
        </section>
      </main>
      <footer className="site-footer"><span>GatorWay · A clearer path through college.</span><span>Built for San Francisco State students</span></footer>
    </div>
  );
}
