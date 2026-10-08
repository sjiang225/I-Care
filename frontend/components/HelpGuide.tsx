"use client";

import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, BookOpen, Check, ClipboardCheck, Compass, UserRound, X } from "lucide-react";

type Topic = "start" | "library" | "assessment" | "account";
type Step = { title: string; image: string; alt: string; highlight: string; instructions: ReactNode; tip: ReactNode };
const TOPICS = [
  { id: "start", label: "Getting started", icon: Compass },
  { id: "library", label: "Guides & videos", icon: BookOpen },
  { id: "assessment", label: "Self-assessment", icon: ClipboardCheck },
  { id: "account", label: "Your account", icon: UserRound },
] as const;

const STEPS: Record<Topic, Step[]> = {
  start: [
    {
      title: "Start with a conversation",
      image: "start", alt: "The Start chatting button on the I-Care home page, outlined in red.", highlight: "Start chatting",
      instructions: <><p>On <strong>Home</strong>, select <strong>Start chatting</strong> to open the message box.</p><p>You can ask a caregiving question or talk about your day.</p></>,
      tip: <>Already started? The button says <strong>Continue chatting</strong>. A topic suggestion on Home fills in a question for you to review before sending.</>,
    },
    {
      title: "Write a question, then send",
      image: "question", alt: "The message box with an example question and the Speak and Send controls.", highlight: "Your question or message → Send",
      instructions: <><p>Type in <strong>Your question or message</strong>, then select <strong>Send</strong>.</p><p>For example: “Where can I find information about sleep?”</p></>,
      tip: <>If <strong>Speak</strong> is available, you can allow microphone access and dictate. Select <strong>Stop</strong>, check the words, then select <strong>Send</strong>. You can always type instead.</>,
    },
    {
      title: "Read the reply and explore",
      image: "reply", alt: "An example reply with a linked citation [1], a Related videos link and a Sources link.", highlight: "Linked numbers, Sources & videos",
      instructions: <><p>Your reply appears in Chat. When provided, select a linked number such as <strong>[1]</strong> or a link under <strong>Sources</strong> to read the original guide.</p><p>Select a title under <strong>Related videos</strong> to watch on YouTube.</p></>,
      tip: <>Resources open in a new browser tab. Close that resource tab, or switch back to the I-Care tab, to return to your conversation.</>,
    },
    {
      title: "Find your way back Home",
      image: "home", alt: "The navigation bar with Home as the first button, followed by Chat, Library and Self-assessment.", highlight: "Home is always at the top",
      instructions: <><p>Select <strong>Home</strong> in the top navigation. To return to your conversation, select <strong>Chat</strong> or <strong>Continue chatting</strong>.</p><p>Your conversation, draft and unfinished assessment stay available as you move between pages while I-Care stays open.</p></>,
      tip: <><strong>New conversation</strong> asks before clearing the current chat and draft. Refreshing or closing I-Care clears unfinished drafts, guest chats and unsubmitted assessment answers.</>,
    },
  ],
  library: [
    {
      title: "Browse by topic or format",
      image: "library", alt: "Library controls: All, Guides, Videos, Search resources and Filter by topic.", highlight: "Library → search or filter",
      instructions: <><p>Select <strong>Library</strong> at the top, or <strong>Browse Library</strong> on Home.</p><p>Choose <strong>All</strong>, <strong>Guides</strong> or <strong>Videos</strong>. Search for a topic such as “sleep”, or use <strong>Filter by topic</strong>.</p></>,
      tip: <>You can search by language, such as “Spanish”. <strong>Clear filters</strong> brings back the full collection.</>,
    },
    {
      title: "Open a guide or video",
      image: "resource", alt: "A library video card with its title, Watch video, YouTube, language and open-in-new-tab icon.", highlight: "Select a resource title",
      instructions: <><p>Check the format and language below a title, then select the title to open the PDF or YouTube video in a new tab.</p><p>Close the resource tab or switch back to I-Care to continue browsing. Your search and filters remain in place.</p></>,
      tip: <>You can browse without sending a chat message. Use <strong>Home</strong> or <strong>Chat</strong> whenever you want to move on.</>,
    },
  ],
  assessment: [
    {
      title: "Choose an optional check-in",
      image: "assessment", alt: "The PHQ-9 assessment card showing the title, description and number of questions.", highlight: "Self-assessment → choose a questionnaire",
      instructions: <><p>Select <strong>Self-assessment</strong> at the top. Choose <strong>PHQ-9</strong> for depression, <strong>GAD-7</strong> for anxiety, or <strong>PSS-10</strong> for perceived stress.</p><p>These questions are about <strong>you, the caregiver</strong>. Taking an assessment is optional.</p></>,
      tip: <>You can continue as a guest without saving results. To save a result to your account, <strong>sign in before starting</strong>.</>,
    },
    {
      title: "Answer at your own pace",
      image: "answer", alt: "A questionnaire question with four response options. No answer is selected.", highlight: "Read the time period, then choose an answer",
      instructions: <><p>Read the instructions and select an answer for each question. Complete the daily-life impact question if it appears.</p><p>At the bottom, select <strong>View my result</strong> as a guest, or <strong>Submit and save my result</strong> when signed in. Your result includes suggested next steps.</p></>,
      tip: <>This is a screening tool, not a diagnosis. Guest results are not saved. You can visit another I-Care page and return, but refreshing or closing I-Care clears unfinished answers.</>,
    },
  ],
  account: [
    {
      title: "Sign in only if you want to save",
      image: "signin", alt: "The Sign in button at the top right of the I-Care page, outlined in red.", highlight: "Sign in, at the top right",
      instructions: <><p>Signing in is optional. You can chat, browse guides and videos, and take a self-assessment as a guest.</p><p>Sign in when you want I-Care to keep your conversations and self-assessment results. Select <strong>Sign in</strong> at the top right.</p></>,
      tip: <>As a guest, nothing is saved: refreshing or closing I-Care clears your chat.</>,
    },
    {
      title: "Sign in or create an account",
      image: "signin-form", alt: "The Welcome back sign-in form with Email and Password fields, a Sign in button and a Create an account link.", highlight: "Enter your email and password",
      instructions: <><p>Enter your email and password, then select <strong>Sign in</strong>.</p><p>First time? Select <strong>Create an account</strong>, then enter your name, email and a password of at least 6 characters.</p></>,
      tip: <>I-Care is a research prototype. Please choose a new password rather than one you use for other accounts.</>,
    },
    {
      title: "Your saved history, and signing out",
      image: "signout", alt: "The top of the page after signing in, with the Sign out button outlined in red.", highlight: "Sign out button",
      instructions: <><p>After you sign in, I-Care opens your most recent saved conversation. New messages and submitted self-assessment results are saved to your account, so you can see them on another device.</p><p>To sign out, select the <strong>Sign out</strong> button at the top right. Your saved history stays in your account.</p></>,
      tip: <>Signing in replaces the guest conversation on screen with your saved one. If you want to keep a conversation, sign in before you start chatting.</>,
    },
  ],
};

export default function HelpGuide({ onClose }: { onClose: () => void }) {
  const [topic, setTopic] = useState<Topic>("start");
  const [step, setStep] = useState(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const steps = STEPS[topic];
  const current = steps[step];

  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog?.showModal();
    headingRef.current?.focus({ preventScroll: true });
    return () => {
      dialog?.close();
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    };
  }, []);

  useLayoutEffect(() => {
    bodyRef.current?.scrollTo(0, 0);
    headingRef.current?.focus({ preventScroll: true });
  }, [topic, step]);

  return <dialog ref={dialogRef} className="help-dialog" aria-labelledby="help-title"
    onKeyDown={(event) => {
      if (event.key !== "Tab") return;
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
      const first = controls[0];
      const last = controls[controls.length - 1];
      // Keep navigation in the guide, including Shift+Tab from the focused heading.
      if (event.shiftKey && (document.activeElement === first || document.activeElement === headingRef.current)) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }}
    onCancel={(event) => { event.preventDefault(); onClose(); }}>
    <div className="help-shell">
      <header className="help-header">
        <div><p className="help-eyebrow">A little guidance, at your pace</p><h2 id="help-title">How to use I-Care</h2></div>
        <button className="help-close" onClick={onClose} aria-label="Close guide"><X size={19} aria-hidden="true" /><span>Close</span></button>
      </header>
      <nav className="help-topics" aria-label="Guide topics">
        {TOPICS.map((item) => <button key={item.id} aria-current={topic === item.id ? "step" : undefined}
          onClick={() => { setTopic(item.id); setStep(0); }}>
          <item.icon size={18} aria-hidden="true" /><span>{item.label}</span>
        </button>)}
      </nav>
      <div className="help-body" ref={bodyRef}>
        <div className="help-progress" aria-hidden="true">{steps.map((_, index) => <span key={index} className={index <= step ? "complete" : ""} />)}</div>
        <h3 ref={headingRef} tabIndex={-1}><span className="help-step-label">Step {step + 1} of {steps.length}</span>{current.title}</h3>
        <div className="help-step-layout">
          <figure className="help-figure">
            <div className="help-highlight"><ArrowDown size={17} aria-hidden="true" />{current.highlight}</div>
            {/* Native screenshots deliberately retain the exact labels of the live UI. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/help/${current.image}.png`} alt={current.alt} />
            <figcaption>Example screen · follow the steps in your own I-Care page</figcaption>
          </figure>
          <div className="help-instructions">{current.instructions}</div>
        </div>
        <aside className="help-tip">{current.tip}</aside>
        {step === steps.length - 1 && topic === "start" && <div className="help-more">
          <p>You can also explore:</p>
          <button onClick={() => { setTopic("library"); setStep(0); }}><BookOpen size={17} aria-hidden="true" /> Guides &amp; videos <ArrowRight size={16} aria-hidden="true" /></button>
          <button onClick={() => { setTopic("assessment"); setStep(0); }}><ClipboardCheck size={17} aria-hidden="true" /> Self-assessment <ArrowRight size={16} aria-hidden="true" /></button>
          <button onClick={() => { setTopic("account"); setStep(0); }}><UserRound size={17} aria-hidden="true" /> Your account <ArrowRight size={16} aria-hidden="true" /></button>
        </div>}
      </div>
      <footer className="help-footer">
        <button className="help-previous" disabled={step === 0} onClick={() => setStep((value) => value - 1)}><ArrowLeft size={18} aria-hidden="true" /> Previous</button>
        {step < steps.length - 1
          ? <button className="help-next" onClick={() => setStep((value) => value + 1)}>Next <ArrowRight size={18} aria-hidden="true" /></button>
          : <button className="help-next" onClick={onClose}>Back to I-Care <Check size={18} aria-hidden="true" /></button>}
      </footer>
    </div>
  </dialog>;
}
