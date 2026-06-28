import type { ChatResponse, HistoryTurn } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function friendlyErrorMessage(status: number): string {
  if (status === 503) return "Document search is temporarily unavailable. Please try again shortly.";
  if (status === 502) return "Our assistant is busy right now. Please try again.";
  return "Something went wrong. Please try again.";
}

export async function sendMessage(query: string, sessionId: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId }),
  });

  if (!res.ok) {
    throw new ApiError(res.status, friendlyErrorMessage(res.status));
  }

  return res.json();
}

export async function fetchHistory(sessionId: string): Promise<HistoryTurn[]> {
  const res = await fetch(`${API_BASE_URL}/history/${sessionId}`);

  if (!res.ok) {
    throw new ApiError(res.status, friendlyErrorMessage(res.status));
  }

  const data = await res.json();
  return data.turns;
}
