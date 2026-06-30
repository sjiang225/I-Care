// Streaming chat client: POSTs to /api/chat and parses the SSE response.

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Source {
  n: number;
  title: string;
  category: string;
  url: string | null;
}

export interface StreamHandlers {
  onDelta: (text: string) => void;
  onSources?: (sources: Source[]) => void;
}

// Streams assistant text deltas + sources; resolves when the stream ends.
export async function streamChat(
  messages: ChatMessage[],
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line.
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const evt of events) {
      let event = "message";
      let data = "";
      for (const line of evt.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const parsed = JSON.parse(data);
      if (event === "delta") handlers.onDelta(parsed.text ?? "");
      else if (event === "sources") handlers.onSources?.(parsed.sources ?? []);
      else if (event === "error") throw new Error(parsed.message ?? "stream error");
    }
  }
}
