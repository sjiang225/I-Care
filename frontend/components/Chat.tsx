"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  HeartHandshake,
  Volume2,
  VolumeX,
  Mic,
  ArrowUp,
  BookOpen,
  House,
  LogOut,
  LogIn,
  MessageCircle,
  SquarePen,
  ClipboardCheck,
  CircleHelp,
  Smartphone,
  Monitor,
} from "lucide-react";
import {
  streamChat,
  type ChatMessage,
  type Source,
  type ResourcesPayload,
} from "@/lib/api";
import {
  me as fetchMe,
  logout as doLogout,
  getHistory,
  type AuthUser,
} from "@/lib/auth";
import ResourceCard from "@/components/ResourceCard";
import BrandMark from "@/components/BrandMark";
import Markdown from "@/components/Markdown";
import LoginRegister from "@/components/auth/LoginRegister";
import SelfAssessment from "@/components/SelfAssessment";
import HomeView from "@/components/HomeView";
import GuideLibrary from "@/components/GuideLibrary";
import HelpGuide from "@/components/HelpGuide";
import { sourceHref } from "@/lib/citations";
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
  resources?: ResourcesPayload;
  peer?: boolean;
};

type View = "home" | "chat" | "library" | "self-assessment";
const FRAME_KEY = "icare:app-frame";

const NAVIGATION = [
  { id: "home", label: "Home", icon: House },
  { id: "chat", label: "Chat", icon: MessageCircle },
  { id: "library", label: "Library", icon: BookOpen },
  { id: "self-assessment", label: "Self-assessment", icon: ClipboardCheck },
] as const;

export default function Chat() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [listening, setListening] = useState(false);
  const [readAloud, setReadAloud] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [view, setView] = useState<View>("home");
  const [assessmentVisited, setAssessmentVisited] = useState(false);
  const [libraryVisited, setLibraryVisited] = useState(false);
  const [resetRequested, setResetRequested] = useState(false);
  const [topicSuggestion, setTopicSuggestion] = useState<string | null>(null);
  const [appFrame, setAppFrame] = useState(false);

  const dictationRef = useRef<Dictation | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string>("");
  const conversationIdRef = useRef<number | null>(null);
  const viewRef = useRef<View>("home");
  const homeRef = useRef<HTMLElement>(null);
  const chatHeadingRef = useRef<HTMLHeadingElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const newChatRef = useRef<HTMLButtonElement>(null);
  const cancelResetRef = useRef<HTMLButtonElement>(null);
  const focusInputRef = useRef(false);
  const homeScrollRef = useRef(0);
  const chatScrollRef = useRef(0);
  const chatNeedsBottomRef = useRef(false);

  function changeView(next: View, focusInput = false) {
    if (viewRef.current === next) {
      if (focusInput) inputRef.current?.focus();
      return;
    }
    if (viewRef.current === "home") homeScrollRef.current = homeRef.current?.scrollTop ?? 0;
    if (viewRef.current === "chat") chatScrollRef.current = scrollRef.current?.scrollTop ?? 0;
    stopSpeaking();
    stopDictation();
    focusInputRef.current = focusInput;
    viewRef.current = next;
    if (next === "self-assessment") setAssessmentVisited(true);
    if (next === "library") setLibraryVisited(true);
    setView(next);
  }

  function navigate(next: View, focusInput = false) {
    if (window.location.hash !== `#${next}`) window.history.pushState(null, "", `#${next}`);
    changeView(next, focusInput);
  }

  useEffect(() => {
    try { setAppFrame(localStorage.getItem(FRAME_KEY) === "1"); } catch {}
  }, []);

  function toggleAppFrame() {
    const next = !appFrame;
    setAppFrame(next);
    try { localStorage.setItem(FRAME_KEY, next ? "1" : "0"); } catch {}
  }

  useEffect(() => {
    const restoreView = () => {
      const hash = window.location.hash.slice(1);
      changeView(hash === "chat" || hash === "self-assessment" || hash === "library" ? hash : "home");
    };
    restoreView();
    window.addEventListener("popstate", restoreView);
    window.addEventListener("hashchange", restoreView);
    return () => {
      window.removeEventListener("popstate", restoreView);
      window.removeEventListener("hashchange", restoreView);
    };
  }, []);

  useLayoutEffect(() => {
    if (view === "home" && homeRef.current) {
      homeRef.current.scrollTop = homeScrollRef.current;
      homeRef.current.querySelector<HTMLElement>("h2")?.focus({ preventScroll: true });
    }
    if (view === "chat") {
      if (scrollRef.current) scrollRef.current.scrollTop = chatNeedsBottomRef.current
        ? scrollRef.current.scrollHeight : chatScrollRef.current;
      chatNeedsBottomRef.current = false;
      if (focusInputRef.current) inputRef.current?.focus();
      else chatHeadingRef.current?.focus({ preventScroll: true });
    }
    focusInputRef.current = false;
  }, [view]);

  useEffect(() => { if (resetRequested) cancelResetRef.current?.focus(); }, [resetRequested]);

  useLayoutEffect(() => {
    const field = inputRef.current;
    if (view !== "chat" || !field) return;
    field.style.height = "auto";
    field.style.height = `${Math.min(Math.max(field.scrollHeight, 44), 140)}px`;
  }, [input, view]);

  useEffect(() => {
    let sid = localStorage.getItem("icare_session_id");
    if (!sid) {
      sid = crypto.randomUUID();
      localStorage.setItem("icare_session_id", sid);
    }
    sessionIdRef.current = sid;
    // Restore session if a valid token exists.
    fetchMe().then((u) => {
      if (u) {
        setUser(u);
        return loadHistory();
      }
    }).catch(() => { /* Guests can continue if account restoration is unavailable. */ });
  }, []);

  async function loadHistory() {
    const h = await getHistory();
    conversationIdRef.current = h.latest_conversation_id;
    if (h.latest_messages.length > 0) {
      setMessages(
        h.latest_messages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
          sources: m.sources,
        }))
      );
    }
  }

  function onLoginSuccess(u: AuthUser) {
    setUser(u);
    setAuthOpen(false);
    setMessages([]);
    setInput("");
    setTopicSuggestion(null);
    setResetRequested(false);
    conversationIdRef.current = null;
    void loadHistory().catch(() => {});
  }

  async function handleLogout() {
    await doLogout();
    setUser(null);
    setMessages([]);
    setInput("");
    setTopicSuggestion(null);
    setResetRequested(false);
    conversationIdRef.current = null;
  }

  // Detect browser speech support AFTER mount only (avoids hydration mismatch).
  const [canSpeechIn, setCanSpeechIn] = useState(false);
  const [canSpeechOut, setCanSpeechOut] = useState(false);
  useEffect(() => {
    setCanSpeechIn(speechSupported());
    setCanSpeechOut(ttsSupported());
  }, []);

  useEffect(() => {
    if (viewRef.current === "chat") scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
    else chatNeedsBottomRef.current = true;
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
      let resources: ResourcesPayload | undefined;
      let peer = false;
      const paint = () =>
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: full,
            sources,
            resources,
            peer,
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
            paint();
          },
          onSignal: (sig) => {
            if (sig && sig.agent === "peer") {
              peer = true;
              paint();
            }
          },
          onResources: (r) => {
            resources = r;
            paint();
          },
          onMeta: (m) => {
            conversationIdRef.current = m.conversation_id;
          },
        },
        sessionIdRef.current,
        conversationIdRef.current
      );
      if (readAloud && full && viewRef.current === "chat") speak(full);
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

  function newChat() {
    if (sending) return;
    stopSpeaking();
    stopDictation();
    setMessages([]);
    setInput("");
    setTopicSuggestion(null);
    setResetRequested(false);
    conversationIdRef.current = null; // next message starts a fresh conversation
    inputRef.current?.focus();
  }

  function chooseTopic(text: string) {
    if (sending) return;
    if (input.trim()) setTopicSuggestion(text);
    else { setInput(text); setTopicSuggestion(null); }
    navigate("chat", true);
  }

  function openHelp() {
    stopSpeaking();
    stopDictation();
    setHelpOpen(true);
  }

  return (
    <div className={appFrame ? "app app-frame" : "app"}>
      {appFrame && <div className="app-view-return">
        <span>App view</span>
        <button className="return-web-btn" onClick={toggleAppFrame}>
          <Monitor size={18} aria-hidden="true" /> Back to web view
        </button>
      </div>}
      <header className="header">
        <div className="brand">
          <BrandMark size={54} />
          <div className="brand-copy">
            <h1>I-Care</h1>
            <p className="brand-tagline">Caregiver Companion</p>
          </div>
        </div>
        <nav className="primary-nav" aria-label="Main navigation">
          {NAVIGATION.map((item) => <button key={item.id} onClick={() => navigate(item.id)}
            aria-current={view === item.id ? "page" : undefined} aria-controls={`panel-${item.id}`}>
            <item.icon size={21} aria-hidden="true" /><span>{item.label}</span>
          </button>)}
        </nav>
        <div className="header-actions">
          {!appFrame && <button className="view-toggle" onClick={toggleAppFrame}
            aria-label="Switch to app view" title="Preview I-Care at phone size">
            <Smartphone size={18} aria-hidden="true" />
            <span className="view-toggle-label">App view</span>
          </button>}
          <button className="help-launcher" onClick={openHelp} aria-haspopup="dialog">
            <CircleHelp size={18} aria-hidden="true" /> Help
          </button>
          {canSpeechOut && view === "chat" && (
            <button
              className={`ghost-btn ${readAloud ? "on" : ""}`}
              onClick={toggleReadAloud}
              aria-label="Read answers aloud"
              title="Read answers aloud"
            >
              {readAloud ? <Volume2 size={20} /> : <VolumeX size={20} />}
            </button>
          )}
          {user ? (
            <button
              className="signin-btn"
              onClick={handleLogout}
              disabled={sending}
              aria-label={`Sign out (${user.display_name})`}
              title={`${user.display_name} · Sign out`}
            >
              <LogOut size={16} /> Sign out
            </button>
          ) : (
            <button
              className="signin-btn"
              onClick={() => setAuthOpen(true)}
              disabled={sending}
              title="Sign in or create an account"
            >
              <LogIn size={16} /> Sign in
            </button>
          )}
        </div>
      </header>

      {authOpen && (
        <LoginRegister
          onSuccess={onLoginSuccess}
          onClose={() => setAuthOpen(false)}
        />
      )}
      {helpOpen && <HelpGuide onClose={() => setHelpOpen(false)} />}

      <main className="app-main">
        <section id="panel-home" className="app-panel home-page" hidden={view !== "home"} ref={homeRef} aria-labelledby="home-heading">
          <HomeView hasConversation={messages.length > 0} hasDraft={Boolean(input.trim())} sending={sending}
            onChat={() => navigate("chat", true)} onAssessment={() => navigate("self-assessment")}
            onLibrary={() => navigate("library")} onTopic={chooseTopic} onHelp={openHelp} />
        </section>
        <section id="panel-chat" className="app-panel chat-page" hidden={view !== "chat"} aria-labelledby="chat-heading">
          <div className="chat-toolbar"><h2 id="chat-heading" ref={chatHeadingRef} tabIndex={-1}>Your conversation</h2>
            {(messages.length > 0 || input.trim()) && <button ref={newChatRef} className="new-chat-btn" onClick={() => setResetRequested(true)} disabled={sending}>
              <SquarePen size={17} aria-hidden="true" /> New conversation
            </button>}
          </div>
          {resetRequested && <div className="chat-choice" role="group" aria-label="Start a new conversation?">
            <strong>Start a new conversation?</strong><p>This clears the conversation and any unfinished message from this screen.</p>
            <div><button ref={cancelResetRef} onClick={() => { setResetRequested(false); newChatRef.current?.focus(); }}>Keep this conversation</button>
              <button onClick={newChat} disabled={sending}>Start new conversation</button></div>
          </div>}
          {topicSuggestion && <div className="chat-choice" role="group" aria-label="Suggested question">
            <strong>You have an unfinished message.</strong><p>Keep your draft, or replace it with this suggestion:</p><p>{topicSuggestion}</p>
            <div><button onClick={() => { setTopicSuggestion(null); inputRef.current?.focus(); }}>Keep my draft</button>
              <button onClick={() => { setInput(topicSuggestion); setTopicSuggestion(null); inputRef.current?.focus(); }}>Use suggested question</button></div>
          </div>}
      <div className="messages" ref={scrollRef}>
        {messages.length === 0 && <div className="chat-empty">
          <MessageCircle size={32} aria-hidden="true" /><h3>What&apos;s on your mind?</h3>
          <p>Type your question below, then select <strong>Send</strong>.</p>
        </div>}

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
                    <Markdown sources={m.sources}>{m.content}</Markdown>
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
                      {sourceHref(s.url) ? (
                        <a href={sourceHref(s.url)!} target="_blank" rel="noreferrer"
                          aria-label={`Source ${s.n}: ${s.title} (opens in a new tab)`}>
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
        <div className="composer-label"><label htmlFor="chat-question">Your question or message</label>{listening && <span role="status">Listening…</span>}</div>
        <div className="composer">
          {canSpeechIn && (
            <button
              className={`round-btn mic labeled-control ${listening ? "on" : ""}`}
              onClick={toggleDictation}
              aria-label={listening ? "Stop dictation" : "Speak"}
              title={listening ? "Stop" : "Speak"}
            >
              <Mic size={19} aria-hidden="true" /><span>{listening ? "Stop" : "Speak"}</span>
            </button>
          )}
          <textarea
            id="chat-question"
            ref={inputRef}
            rows={1}
            placeholder="Type here…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit(input);
              }
            }}
          />
          <button
            className="round-btn send labeled-control"
            onClick={() => submit(input)}
            disabled={sending || !input.trim()}
            aria-label="Send"
          >
            <ArrowUp size={19} aria-hidden="true" /><span>Send</span>
          </button>
        </div>
      </div>
        </section>
        <section id="panel-library" className="app-panel library-panel" hidden={view !== "library"} aria-labelledby="library-heading">
          {libraryVisited && <GuideLibrary visible={view === "library"} />}
        </section>
        <section id="panel-self-assessment" className="app-panel sa-panel" hidden={view !== "self-assessment"} aria-label="Self-assessment">
          {assessmentVisited && <SelfAssessment key={user?.id ?? "guest"} user={user} visible={view === "self-assessment"} />}
        </section>
      </main>
        {/* Home has its own footer beneath the urgent-help section. */}
        {view !== "home" && <footer className="footer app-footer">
          I-Care is an educational tool, not medical advice. In an emergency, call{" "}
          <a className="footer-call" href="tel:911">911</a>.
          <br />
          ©2026 Rutgers, The State University of New Jersey. All rights reserved.
        </footer>}
    </div>
  );
}
