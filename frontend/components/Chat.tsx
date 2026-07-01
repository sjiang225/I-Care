"use client";

import { useEffect, useRef, useState } from "react";
import {
  streamChat,
  type ChatMessage,
  type Source,
  type ResourcesPayload,
} from "@/lib/api";
import WellbeingView from "@/components/WellbeingView";
import ResourceCard from "@/components/ResourceCard";
import {
  speechSupported,
  ttsSupported,
  startDictation,
  speak,
  stopSpeaking,
  type Dictation,
} from "@/lib/speech";

const GREETING =
  "Hi, I'm I-Care. I'm here to support you as a dementia caregiver. " +
  "Ask me anything — about behaviors, daily care, or how you're feeling.";

type UiMessage = ChatMessage & {
  sources?: Source[];
  wellbeingLogged?: boolean;
  resources?: ResourcesPayload;
};

export default function Chat() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [listening, setListening] = useState(false);
  const [readAloud, setReadAloud] = useState(false);
  const [view, setView] = useState<"chat" | "wellbeing">("chat");

  const dictationRef = useRef<Dictation | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string>("");

  // Stable per-device session id so well-being can be tracked over time.
  useEffect(() => {
    let sid = localStorage.getItem("icare_session_id");
    if (!sid) {
      sid = crypto.randomUUID();
      localStorage.setItem("icare_session_id", sid);
    }
    sessionIdRef.current = sid;
  }, []);

  const canSpeechIn = speechSupported();
  const canSpeechOut = ttsSupported();

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages, sending]);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    stopDictation();

    const next: UiMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setSending(true);

    // Placeholder assistant bubble we stream into.
    setMessages((m) => [...m, { role: "assistant", content: "" }]);

    try {
      let full = "";
      let sources: Source[] | undefined;
      let wellbeingLogged = false;
      let resources: ResourcesPayload | undefined;
      const paint = () =>
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: full,
            sources,
            wellbeingLogged,
            resources,
          };
          return copy;
        });
      await streamChat(
        next.map((m) => ({ role: m.role, content: m.content })),
        {
          onDelta: (delta) => {
            full += delta;
            paint();
          },
          onSources: (s) => {
            sources = s;
          },
          onSignal: (sig) => {
            if (sig && "wellbeing" in sig) wellbeingLogged = true;
          },
          onResources: (r) => {
            resources = r;
            paint();
          },
        },
        sessionIdRef.current
      );
      if (readAloud && full) speak(full);
    } catch (err) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = {
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
        };
        return copy;
      });
    } finally {
      setSending(false);
    }
  }

  function toggleDictation() {
    if (listening) {
      stopDictation();
      return;
    }
    const d = startDictation(
      (text, isFinal) => {
        setInput(text);
        if (isFinal) stopDictation();
      },
      () => setListening(false)
    );
    if (d) {
      dictationRef.current = d;
      setListening(true);
    }
  }

  function stopDictation() {
    dictationRef.current?.stop();
    dictationRef.current = null;
    setListening(false);
  }

  function toggleReadAloud() {
    if (readAloud) stopSpeaking();
    setReadAloud((v) => !v);
  }

  if (view === "wellbeing") {
    return (
      <WellbeingView
        sessionId={sessionIdRef.current}
        onBack={() => setView("chat")}
      />
    );
  }

  return (
    <div className="app">
      <header className="header">
        <span aria-hidden style={{ fontSize: "1.6rem" }}>🤝</span>
        <div>
          <h1>I-Care</h1>
          <div className="tag">Dementia Caregiver Companion</div>
        </div>
        <button
          className="icon-btn"
          style={{ marginLeft: "auto" }}
          onClick={() => setView("wellbeing")}
          aria-label="View your well-being trend"
          title="Your well-being"
        >
          📈
        </button>
        {canSpeechOut && (
          <button
            className={`icon-btn ${readAloud ? "active" : ""}`}
            style={{ background: readAloud ? "#fff" : undefined }}
            onClick={toggleReadAloud}
            aria-label="Read answers aloud"
            title="Read answers aloud"
          >
            {readAloud ? "🔊" : "🔇"}
          </button>
        )}
      </header>

      <div className="messages" ref={scrollRef}>
        {messages.length === 0 && <div className="empty">{GREETING}</div>}
        {messages.map((m, i) => (
          <div key={i} className={`turn ${m.role}`}>
            <div className={`bubble ${m.role}`}>
              {m.content || (sending && i === messages.length - 1 ? "…" : "")}
            </div>
            {m.role === "assistant" && m.wellbeingLogged && (
              <button
                className="wb-noted"
                onClick={() => setView("wellbeing")}
                title="View your well-being trend"
              >
                💚 Noted how you&apos;re feeling — view trend
              </button>
            )}
            {m.role === "assistant" && m.resources && (
              <ResourceCard resources={m.resources} />
            )}
            {m.role === "assistant" && m.sources && m.sources.length > 0 && (
              <div className="sources">
                <span className="sources-label">Sources</span>
                {m.sources.map((s) => (
                  <span key={s.n} className="source-chip">
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noreferrer">
                        [{s.n}] {s.title}
                      </a>
                    ) : (
                      <>
                        [{s.n}] {s.title}
                      </>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="composer">
        {canSpeechIn && (
          <button
            className={`icon-btn ${listening ? "active" : ""}`}
            onClick={toggleDictation}
            aria-label={listening ? "Stop dictation" : "Speak"}
            title={listening ? "Stop" : "Speak"}
          >
            🎤
          </button>
        )}
        <textarea
          rows={1}
          placeholder="Type or speak your question…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button
          className="send-btn"
          onClick={send}
          disabled={sending || !input.trim()}
          aria-label="Send"
        >
          ➤
        </button>
      </div>

      <footer className="footer">
        ©2026 Rutgers, The State University of New Jersey, All rights reserved. Do
        not copy or reproduce without permission.
        <br />
        I-Care is an educational tool, not medical advice. In an emergency call 911.
      </footer>
    </div>
  );
}
