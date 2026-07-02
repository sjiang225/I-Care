// Streaming chat client: POSTs to /api/chat and parses the SSE response.

import { authHeaders } from "./auth";

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

export interface Helpline {
  name: string;
  phone: string;
  url: string;
  description: string;
}
export interface Facility {
  name: string;
  city: string;
  county: string;
}
export interface VideoLink {
  title: string;
  url: string;
}
export interface ResourcesPayload {
  helplines: Helpline[];
  facilities: Facility[];
  facilities_note: string;
  videos: VideoLink[];
}

export interface StreamHandlers {
  onDelta: (text: string) => void;
  onSources?: (sources: Source[]) => void;
  onSignal?: (signal: Record<string, unknown>) => void;
  onResources?: (resources: ResourcesPayload) => void;
  onMeta?: (meta: { conversation_id: number }) => void;
}

export interface WellbeingPoint {
  ts: number;
  stress_level: number;
  emotions: string[];
  note: string;
}

export interface WellbeingData {
  session_id: string;
  points: WellbeingPoint[];
  summary: {
    count: number;
    avg_stress: number;
    latest_stress: number | null;
    trend: "up" | "down" | "steady";
    top_emotions: [string, number][];
  };
}

export async function getWellbeing(sessionId: string): Promise<WellbeingData> {
  const res = await fetch(
    `/api/wellbeing?session_id=${encodeURIComponent(sessionId)}`,
    { headers: authHeaders() }
  );
  if (!res.ok) throw new Error(`Wellbeing request failed: ${res.status}`);
  return res.json();
}

// Streams assistant text deltas + sources; resolves when the stream ends.
export async function streamChat(
  messages: ChatMessage[],
  handlers: StreamHandlers,
  sessionId: string,
  conversationId: number | null,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      messages,
      session_id: sessionId,
      conversation_id: conversationId,
    }),
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
      else if (event === "resources") handlers.onResources?.(parsed);
      else if (event === "signal") handlers.onSignal?.(parsed);
      else if (event === "meta") handlers.onMeta?.(parsed);
      else if (event === "error") throw new Error(parsed.message ?? "stream error");
    }
  }
}
