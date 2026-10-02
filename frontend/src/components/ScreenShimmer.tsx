"use client";

import { motion } from "motion/react";

/** A single soft light sweep across the whole screen, played once when personalising finishes. Decorative and never blocks the page. */
export function ScreenShimmer() {
  return <motion.div data-testid="screen-shimmer" aria-hidden="true" className="screen-shimmer" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} />;
}
