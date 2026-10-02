"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtUnits } from "@/lib/format";
import type { GeCourse } from "@/lib/types";

/** The courses that count for the given GE areas, with a filter. */
export function GeList({ areas }: { areas: string[] }) {
  const key = areas.join(",");
  const [loaded, setLoaded] = useState<{ key: string; items: GeCourse[] } | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!key) return;
    let alive = true;
    api
      .geCourses(key.split(","))
      .then((r) => {
        if (alive) setLoaded({ key, items: r.courses });
      })
      .catch(() => {
        if (!alive) return;
        setError("We couldn't load the course list.");
        setLoaded({ key, items: [] });
      });
    return () => {
      alive = false;
    };
  }, [key]);

  if (!key) return <p className="text-sm text-muted">We don&apos;t have a course list for this area.</p>;
  const items = loaded?.key === key ? loaded.items : null;
  const needle = filter.trim().toLowerCase();
  const shown = items?.filter((c) => !needle || `${c.code} ${c.title}`.toLowerCase().includes(needle));

  return (
    <div>
      <input
        aria-label="Filter courses"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter by name or code"
        className="w-full rounded-full border border-line bg-white/80 px-4 py-2.5 text-sm outline-none transition focus:border-purple/40 focus:ring-4 focus:ring-purple-soft"
      />
      {error && (
        <p role="alert" className="mt-3 rounded-2xl bg-gold-soft px-4 py-3 text-sm text-[#6b5a2a]">
          {error}
        </p>
      )}
      <ul className="mt-4 flex flex-col gap-3">
        {items === null && [0, 1, 2].map((i) => <li key={i} className="h-20 animate-shimmer rounded-2xl bg-gradient-to-r from-purple-soft/40 via-white to-purple-soft/40 bg-[length:200%_100%]" />)}
        {items?.length === 0 && !error && <li className="text-sm text-muted">No courses are labelled for this area yet.</li>}
        {items && items.length > 0 && shown?.length === 0 && <li className="text-sm text-muted">No courses match that filter.</li>}
        {shown?.map((c) => (
          <li key={c.code} className="rounded-2xl border border-line bg-white/80 p-4">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted">
              {c.code} · {fmtUnits(c.units_min)} units
            </p>
            <p className="mt-0.5 font-serif text-[1.02rem] leading-snug">{c.title}</p>
            {c.description && <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted">{c.description}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
