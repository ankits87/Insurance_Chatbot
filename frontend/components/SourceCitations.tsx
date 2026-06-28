"use client";

import { useState } from "react";
import type { Source } from "@/lib/types";

export function SourceCitations({ sources }: { sources: Source[] }) {
  const [expanded, setExpanded] = useState(false);

  if (sources.length === 0) return null;

  return (
    <div className="mt-2 text-sm">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="min-h-[44px] text-zinc-500 underline underline-offset-2 hover:text-zinc-700"
      >
        {expanded ? "Hide sources" : `Sources (${sources.length})`}
      </button>
      {expanded && (
        <ul className="mt-2 space-y-1 text-zinc-600">
          {sources.map((source, i) => (
            <li key={i}>
              <span className="font-medium text-zinc-700">{source.product_name}</span>
              {": "}
              {[source.section, source.subsection, source.topic].filter(Boolean).join(" > ")}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
