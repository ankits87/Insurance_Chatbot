import type { Message } from "@/lib/types";
import { SourceCitations } from "./SourceCitations";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-900"
        }`}
      >
        {!isUser && message.products && message.products.length > 0 && (
          <div className="mb-1 flex flex-wrap gap-1">
            {message.products.map((product) => (
              <span
                key={product}
                className="rounded-full bg-zinc-200 px-2 py-0.5 text-xs font-medium text-zinc-700"
              >
                {product}
              </span>
            ))}
          </div>
        )}
        <p className="whitespace-pre-wrap">{message.text}</p>
        {!isUser && message.sources && <SourceCitations sources={message.sources} />}
      </div>
    </div>
  );
}
