"use client";

import { useEffect, useRef, useState } from "react";
import {
  HeartHandshake,
  LineChart,
  Volume2,
  VolumeX,
  Mic,
  ArrowUp,
  Brain,
  Heart,
  Moon,
  MapPin,
  BookOpen,
} from "lucide-react";
import {
  streamChat,
  type ChatMessage,
  type Source,
  type ResourcesPayload,
} from "@/lib/api";
import WellbeingView from "@/components/WellbeingView";
import ResourceCard from "@/components/ResourceCard";
import BrandMark from "@/components/BrandMark";
import Markdown from "@/components/Markdown";
import {
  speechSupported,
  ttsSupported,
  startDictation,
  speak,
  stopSpeaking,
  type Dictation,
} from "@/lib/speech";

type UiMessage = ChatMessage & {
  sources?: Source[];
  wellbeingLogged?: boolean;
  resources?: ResourcesPayload;
};

const SUGGESTED = [
  {
    icon: Brain,
    label: "Managing difficult behaviors",
    text: "How do I handle challenging behaviors like agitation or aggression?",
  },
  {
    icon: Heart,
    label: "I'm feeling overwhelmed",
    text: "I feel overwhelmed and exhausted as a caregiver.",
  },
  {
    icon: Moon,
    label: "Sleep problems",
    text: "My loved one is up all night. What can I do?",
  },
  {
    icon: MapPin,
    label: "Find local care in NJ",
    text: "How do I find memory care near me in New Jersey?",
  },
];

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

  useEffect(() => {
    let sid = localStorage.getItem("icare_session_id");
    if (!sid) {
      sid = crypto.randomUUID();
      localStorage.setItem("icare_session_id", sid);
    }
    sessionIdRef.current = sid;
  }, []);

  // Detect browser speech support AFTER mount only (avoids hydration mismatch).
  const [canSpeechIn, setCanSpeechIn] = useState(false);
  const [canSpeechOut, setCanSpeechOut] = useState(false);
  useEffect(() => {
    setCanSpeechIn(speechSupported());
    setCanSpeechOut(ttsSupported());
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages, sending]);

  async function submit(text: string) {
    const t = text.trim();
    if (!t || sending) return;
    stopDictation();

    const next: UiMessage[] = [...messages, { role: "user", content: t }];
    setMessages(next);
    setInput("");
    setSending(true);
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
    } catch {
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
    if (listening) return stopDictation();
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
        <BrandMark size={42} />
        <div>
          <h1>I-Care</h1>
          <div className="status">
            <span className="status-dot" /> Online · Caregiver Companion
          </div>
        </div>
        <div className="header-actions">
          <button
            className="ghost-btn"
            onClick={() => setView("wellbeing")}
            aria-label="Your well-being"
            title="Your well-being"
          >
            <LineChart size={20} />
          </button>
          {canSpeechOut && (
            <button
              className={`ghost-btn ${readAloud ? "on" : ""}`}
              onClick={toggleReadAloud}
              aria-label="Read answers aloud"
              title="Read answers aloud"
            >
              {readAloud ? <Volume2 size={20} /> : <VolumeX size={20} />}
            </button>
          )}
        </div>
      </header>

      <div className="messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="welcome">
            <BrandMark large />
            <h2>Hi, I&apos;m I-Care</h2>
            <p>
              Your companion for dementia caregiving. Ask me anything — about
              behaviors, daily care, local resources, or how you&apos;re feeling.
            </p>
            <div className="prompt-chips">
              {SUGGESTED.map((s) => (
                <button
                  key={s.label}
                  className="prompt-chip"
                  onClick={() => submit(s.text)}
                >
                  <s.icon size={17} />
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`turn ${m.role}`}>
            {m.role === "assistant" && (
              <div className="msg-avatar">
                <HeartHandshake size={18} />
              </div>
            )}
            <div className="col">
              <div className={`bubble ${m.role}`}>
                {m.content ? (
                  m.role === "assistant" ? (
                    <Markdown>{m.content}</Markdown>
                  ) : (
                    m.content
                  )
                ) : sending && i === messages.length - 1 ? (
                  <span className="typing">
                    <span />
                    <span />
                    <span />
                  </span>
                ) : (
                  ""
                )}
              </div>

              {m.role === "assistant" && m.wellbeingLogged && (
                <button className="wb-noted" onClick={() => setView("wellbeing")}>
                  <Heart size={13} /> Noted how you&apos;re feeling — view trend
                </button>
              )}
              {m.role === "assistant" && m.resources && (
                <ResourceCard resources={m.resources} />
              )}
              {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                <div className="sources">
                  <span className="sources-label">
                    <BookOpen size={13} /> Sources
                  </span>
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
          </div>
        ))}
      </div>

      <div className="composer-wrap">
        <div className="composer">
          {canSpeechIn && (
            <button
              className={`round-btn mic ${listening ? "on" : ""}`}
              onClick={toggleDictation}
              aria-label={listening ? "Stop dictation" : "Speak"}
              title={listening ? "Stop" : "Speak"}
            >
              <Mic size={20} />
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
                submit(input);
              }
            }}
          />
          <button
            className="round-btn send"
            onClick={() => submit(input)}
            disabled={sending || !input.trim()}
            aria-label="Send"
          >
            <ArrowUp size={20} />
          </button>
        </div>
        <div className="footer">
          I-Care is an educational tool, not medical advice. In an emergency call
          911.
          <br />
          ©2026 Rutgers, The State University of New Jersey. All rights reserved.
        </div>
      </div>
    </div>
  );
}
