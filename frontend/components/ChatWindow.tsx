import type { Message } from "@/lib/types";
import { MessageBubble } from "./MessageBubble";

export function ChatWindow({
  messages,
  loading,
  thinking,
}: {
  messages: Message[];
  loading: boolean;
  thinking: boolean;
}) {
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-400">
        Loading conversation...
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-center px-6 text-zinc-400">
        Ask me anything about your policy documents.
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      {messages.map((message, i) => (
        <MessageBubble key={i} message={message} />
      ))}
      {thinking && (
        <div className="flex justify-start">
          <div className="rounded-2xl bg-zinc-100 px-4 py-3 text-zinc-500">Thinking...</div>
        </div>
      )}
    </div>
  );
}
