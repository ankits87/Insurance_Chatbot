"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ChatWindow } from "@/components/ChatWindow";
import { ChatInput } from "@/components/ChatInput";
import { Sidebar } from "@/components/Sidebar";
import { fetchHistory, sendMessage, ApiError } from "@/lib/api";
import {
  getAllSessions,
  getActiveSessionId,
  createNewSession,
  setActiveSession,
  updateSessionTitle,
  type SessionMeta,
} from "@/lib/session";
import type { Message } from "@/lib/types";

export default function Home() {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isFirstMessage = useRef(true);

  useEffect(() => {
    const id = getActiveSessionId();
    setActiveId(id);
    setSessions(getAllSessions());
    loadSessionHistory(id);
  }, []);

  function loadSessionHistory(sessionId: string) {
    setLoadingHistory(true);
    fetchHistory(sessionId)
      .then((turns) => {
        const history = turns.flatMap((turn): Message[] => [
          { role: "user", text: turn.query },
          { role: "assistant", text: turn.answer, sources: turn.sources, products: turn.products },
        ]);
        setMessages(history);
        isFirstMessage.current = history.length === 0;
      })
      .catch((err) => {
        const message = err instanceof ApiError ? err.message : "Could not load chat history.";
        toast.error(message);
        setMessages([]);
        isFirstMessage.current = true;
      })
      .finally(() => setLoadingHistory(false));
  }

  function handleSelectSession(id: string) {
    setActiveSession(id);
    setActiveId(id);
    setMessages([]);
    setSidebarOpen(false);
    loadSessionHistory(id);
  }

  function handleNewChat() {
    const id = createNewSession();
    setActiveId(id);
    setMessages([]);
    setSessions(getAllSessions());
    setSidebarOpen(false);
    setLoadingHistory(false);
    isFirstMessage.current = true;
  }

  async function handleSend(text: string) {
    if (!activeId) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setThinking(true);

    try {
      const response = await sendMessage(text, activeId);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: response.answer,
          sources: response.sources,
          products: response.products,
        },
      ]);

      if (isFirstMessage.current) {
        updateSessionTitle(activeId, text);
        setSessions(getAllSessions());
        isFirstMessage.current = false;
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      toast.error(message);
    } finally {
      setThinking(false);
    }
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelectSession}
        onNewChat={handleNewChat}
      />

      <div className="flex flex-1 flex-col min-w-0">
        <header className="flex items-center gap-3 border-b border-zinc-200 px-4 py-3 md:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded p-1.5 text-zinc-600 hover:bg-zinc-100"
            aria-label="Open menu"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="font-semibold text-zinc-900">Policy Assistant</span>
        </header>

        <div className="flex flex-1 flex-col max-w-2xl w-full mx-auto overflow-hidden">
          <ChatWindow messages={messages} loading={loadingHistory} thinking={thinking} />
          <ChatInput onSend={handleSend} disabled={loadingHistory || thinking} />
        </div>
      </div>
    </div>
  );
}
