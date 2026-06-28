"use client";

import { useState } from "react";

export function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled: boolean;
}) {
  const [text, setText] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-4 border-t border-zinc-200">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        placeholder="Ask about your policy..."
        className="flex-1 min-h-[44px] rounded-full border border-zinc-300 px-4 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="min-h-[44px] min-w-[44px] rounded-full bg-zinc-900 px-5 text-white disabled:opacity-50"
      >
        Send
      </button>
    </form>
  );
}
