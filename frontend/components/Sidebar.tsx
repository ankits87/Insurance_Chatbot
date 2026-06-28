"use client";

import type { SessionMeta } from "@/lib/session";

function dayLabel(dateStr: string): string {
  const date = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  if (sameDay(date, today)) return "Today";
  if (sameDay(date, yesterday)) return "Yesterday";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function groupSessions(sessions: SessionMeta[]): { label: string; items: SessionMeta[] }[] {
  const map = new Map<string, SessionMeta[]>();
  for (const s of sessions) {
    const label = dayLabel(s.createdAt);
    if (!map.has(label)) map.set(label, []);
    map.get(label)!.push(s);
  }
  return Array.from(map.entries()).map(([label, items]) => ({ label, items }));
}

export function Sidebar({
  open,
  onClose,
  sessions,
  activeId,
  onSelect,
  onNewChat,
}: {
  open: boolean;
  onClose: () => void;
  sessions: SessionMeta[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}) {
  const groups = groupSessions(sessions);

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-64 shrink-0 flex-col bg-zinc-900 text-white transition-transform duration-200 md:static md:z-auto md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-zinc-700 px-4 py-4">
          <span className="text-sm font-semibold">Policy Assistant</span>
          <button
            onClick={onClose}
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded p-1 text-zinc-400 hover:text-white md:hidden"
            aria-label="Close sidebar"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-3 pt-3">
          <button
            onClick={onNewChat}
            className="flex min-h-[44px] w-full items-center gap-2 rounded-lg border border-zinc-600 px-3 py-2 text-sm text-zinc-200 transition-colors hover:bg-zinc-800"
          >
            <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New chat
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-3 pb-4 pt-4">
          {groups.length === 0 && (
            <p className="px-1 text-xs text-zinc-500">No past chats yet.</p>
          )}
          {groups.map(({ label, items }) => (
            <div key={label}>
              <p className="mb-1 px-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                {label}
              </p>
              <ul className="space-y-0.5">
                {items.map((s) => (
                  <li key={s.id}>
                    <button
                      onClick={() => onSelect(s.id)}
                      className={`flex min-h-[44px] w-full items-center rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                        s.id === activeId
                          ? "bg-zinc-700 text-white"
                          : "text-zinc-300 hover:bg-zinc-800 hover:text-white"
                      }`}
                    >
                      <span className="truncate">{s.title}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}
