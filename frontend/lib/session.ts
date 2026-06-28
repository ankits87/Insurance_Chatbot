const SESSIONS_KEY = "chatSessions";
const ACTIVE_KEY = "activeChatSessionId";
const LEGACY_KEY = "chatSessionId";

export interface SessionMeta {
  id: string;
  title: string;
  createdAt: string;
}

function saveSessions(sessions: SessionMeta[]): void {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

export function getAllSessions(): SessionMeta[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (raw) return JSON.parse(raw) as SessionMeta[];

    const legacyId = localStorage.getItem(LEGACY_KEY);
    if (legacyId) {
      const migrated: SessionMeta[] = [
        { id: legacyId, title: "Previous chat", createdAt: new Date().toISOString() },
      ];
      saveSessions(migrated);
      localStorage.removeItem(LEGACY_KEY);
      return migrated;
    }

    return [];
  } catch {
    return [];
  }
}

export function getActiveSessionId(): string {
  const active = localStorage.getItem(ACTIVE_KEY);
  if (active) return active;
  return createNewSession();
}

export function createNewSession(): string {
  const id = crypto.randomUUID();
  const session: SessionMeta = { id, title: "New chat", createdAt: new Date().toISOString() };
  saveSessions([session, ...getAllSessions()]);
  localStorage.setItem(ACTIVE_KEY, id);
  return id;
}

export function setActiveSession(id: string): void {
  localStorage.setItem(ACTIVE_KEY, id);
}

export function updateSessionTitle(id: string, title: string): void {
  const sessions = getAllSessions();
  const idx = sessions.findIndex((s) => s.id === id);
  if (idx !== -1 && sessions[idx].title === "New chat") {
    sessions[idx] = { ...sessions[idx], title: title.slice(0, 45) };
    saveSessions(sessions);
  }
}
