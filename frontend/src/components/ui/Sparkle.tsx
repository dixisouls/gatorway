"use client";

import { motion } from "motion/react";

/** The decorative AI star. `spin` makes it slowly turn and breathe (use while the AI is working). */
export function Sparkle({ size = 18, spin = false, className = "" }: { size?: number; spin?: boolean; className?: string }) {
  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      animate={spin ? { rotate: [0, 90, 180], scale: [1, 1.18, 1] } : undefined}
      transition={spin ? { duration: 2.4, repeat: Infinity, ease: "easeInOut" } : undefined}
    >
      <path fill="currentColor" d="M12 2c.6 5.4 4.6 9.4 10 10-5.4.6-9.4 4.6-10 10-.6-5.4-4.6-9.4-10-10 5.4-.6 9.4-4.6 10-10z" />
    </motion.svg>
  );
}
