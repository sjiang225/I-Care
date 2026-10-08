"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, ClipboardCheck, HeartHandshake, History, Phone, ExternalLink } from "lucide-react";
import { getInstruments, getAssessmentHistory, submitAssessment, type Instrument, type AssessmentResult } from "@/lib/assessments";
import type { AuthUser } from "@/lib/auth";

function ScreeningNote() {
  return <div className="sa-note">
    <strong>Please remember that this is a screening tool, not a diagnosis.</strong>{" "}
    If you have concerns about your mental health or well-being, we encourage you
    to seek guidance from a qualified healthcare professional.
  </div>;
}

function SafetySupport() {
  return <aside className="sa-support" role="alert">
    <h3><HeartHandshake size={22} /> Support is available now</h3>
    <p>Thank you for sharing this. Please contact a qualified healthcare professional
      promptly to discuss these thoughts, regardless of your total score.</p>
    <p>If you need immediate emotional support in the U.S., call or text <strong>988</strong>.
      If you are in immediate danger or may act on these thoughts, call <strong>911</strong> or go to the nearest emergency department.</p>
    <div className="sa-links">
      <a href="tel:988"><Phone size={16} /> Call 988</a>
      <a href="sms:988">Text 988</a>
      <a href="https://988lifeline.org/get-help/" target="_blank" rel="noreferrer">988 online support <ExternalLink size={14} /></a>
      <a href="tel:911">Call 911</a>
    </div>
    <p className="sa-small">This assessment is not monitored in real time. I-Care does not contact emergency services for you.</p>
  </aside>;
}

function Sources({ source }: { source: Pick<Instrument, "source_pdf" | "source_url" | "attribution"> }) {
  return <div className="sa-sources">
    <div className="sa-links">
      <a href={source.source_pdf} target="_blank" rel="noreferrer">Original questionnaire (PDF) <ExternalLink size={14} /></a>
      <a href={source.source_url} target="_blank" rel="noreferrer">About this questionnaire <ExternalLink size={14} /></a>
    </div>
    <p>{source.attribution}</p>
  </div>;
}

function dateText(ts: number) {
  return new Date(ts * 1000).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export default function SelfAssessment({ user, visible }: { user: AuthUser | null; visible: boolean }) {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [screen, setScreen] = useState<"menu" | "form" | "result" | "history">("menu");
  const [active, setActive] = useState<Instrument | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [difficulty, setDifficulty] = useState<number | null>(null);
  const [submissionId, setSubmissionId] = useState("");
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<AssessmentResult[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const submitLock = useRef(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const questionRefs = useRef<(HTMLFieldSetElement | null)[]>([]);
  const difficultyRef = useRef<HTMLFieldSetElement>(null);
  const answered = answers.filter((a) => a !== null).length;
  const dirty = active !== null && answered > 0 && result === null;
  const needsDifficulty = Boolean(active?.difficulty_question && answers.some((a) => a !== null && a > 0));
  const showSafety = active?.safety_item_index != null && (answers[active.safety_item_index] ?? 0) > 0;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError("");
    getInstruments(controller.signal).then(setInstruments).catch(() => {
      if (!controller.signal.aborted) setLoadError("The questionnaires could not be loaded. Please try again.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: 0 });
    if (visible) headingRef.current?.focus({ preventScroll: true });
  }, [screen, active?.id]);

  useEffect(() => {
    if (visible) headingRef.current?.focus({ preventScroll: true });
  }, [visible]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function start(instrument: Instrument) {
    if (active?.id === instrument.id && result === null) {
      setScreen("form");
      return;
    }
    if (dirty && !window.confirm("Start a different assessment? Your unfinished answers will not be saved.")) return;
    setActive(instrument);
    setAnswers(Array(instrument.questions.length).fill(null));
    setDifficulty(null);
    setSubmissionId(crypto.randomUUID());
    setResult(null);
    setError("");
    setScreen("form");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!active || submitLock.current) return;
    const missing = answers.findIndex((a) => a === null);
    if (missing !== -1) {
      setError(`Please answer question ${missing + 1} before viewing your result.`);
      questionRefs.current[missing]?.focus();
      questionRefs.current[missing]?.scrollIntoView({ block: "center" });
      return;
    }
    if (needsDifficulty && difficulty === null) {
      setError("Please answer the question about the impact on daily life.");
      difficultyRef.current?.focus();
      difficultyRef.current?.scrollIntoView({ block: "center" });
      return;
    }
    submitLock.current = true;
    setBusy(true);
    setError("");
    try {
      const scored = await submitAssessment({
        instrument_id: active.id, instrument_version: active.version,
        answers: answers as number[], difficulty: needsDifficulty ? difficulty : null,
        submission_id: submissionId, save: Boolean(user),
      });
      setResult(scored);
      setScreen("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your result could not be loaded. Your answers are still here; please try again.");
    } finally {
      submitLock.current = false;
      setBusy(false);
    }
  }

  async function openHistory() {
    setScreen("history");
    setHistoryLoading(true);
    setHistoryError("");
    try { setHistory(await getAssessmentHistory()); }
    catch (err) { setHistoryError(err instanceof Error ? err.message : "Could not load saved results."); }
    finally { setHistoryLoading(false); }
  }

  const heading = screen === "menu" ? "Mental Health Assessment"
    : screen === "form" ? active?.title
    : screen === "history" ? "Your saved assessments" : "Your assessment result";

  return <div className="sa-body" ref={bodyRef}>
      {screen !== "menu" && <button className="sa-back" disabled={busy} onClick={() => setScreen("menu")}>
        <ArrowLeft size={16} /> All assessments
      </button>}
      <div className="sa-eyebrow"><ClipboardCheck size={17} /> A moment for yourself</div>
      <h2 className="sa-heading" ref={headingRef} tabIndex={-1}>{heading}</h2>

      {screen === "menu" && <>
        <p className="sa-intro">Many people turn to mental health screening tools when they are unsure whether
          what they are experiencing is typical stress or something that may benefit from professional support.
          This assessment can offer helpful insight into your current well-being and help you consider
          appropriate next steps for emotional support and care.</p>
        <p className="sa-small">These questions are about <strong>you, the caregiver</strong>. Participation is optional.
          You can use I-Care without completing an assessment.</p>
        {loading && <p role="status">Loading questionnaires…</p>}
        {loadError && <div className="sa-error" role="alert">{loadError} <button onClick={() => setReloadKey((n) => n + 1)}>Try again</button></div>}
        <div className="sa-catalog">
          {instruments.map((instrument) => <button className="sa-instrument" key={instrument.id} onClick={() => start(instrument)}>
            <span className="sa-instrument-icon"><ClipboardCheck size={24} /></span>
            <span className="sa-instrument-copy"><strong>{instrument.title}</strong><span>{instrument.description}</span>
              <small>{instrument.questions.length} questions · {instrument.recall.toLowerCase()}{active?.id === instrument.id && dirty ? " · Continue unfinished assessment" : ""}</small>
            </span><ArrowRight size={20} />
          </button>)}
        </div>
        <ScreeningNote />
        <div className="sa-storage">
          <p>{user ? "When you submit an assessment, your result and answers are saved to your account. You can return to your saved results here."
            : "You can complete an assessment as a guest. Your answers are sent for scoring when you submit, but are not saved. Sign in before starting if you want to save your result."}</p>
          {user && <button className="sa-secondary" onClick={openHistory}><History size={18} /> View saved results</button>}
        </div>
      </>}

      {screen === "form" && active && <>
        <p className="sa-intro">{active.instructions}</p>
        <p className="sa-small">You can visit Home or Chat and come back to finish. Refreshing or closing this page clears unfinished answers.</p>
        <div className="sa-progress"><span aria-live="polite">{answered} of {active.questions.length} questions answered</span>
          <progress aria-label="Questions answered" value={answered} max={active.questions.length} /></div>
        <form onSubmit={submit} noValidate>
          {active.questions.map((question, index) => <div key={`${active.id}-${index}`}>
            <fieldset className={`sa-question${error && answers[index] === null ? " sa-missing" : ""}`} disabled={busy}
              tabIndex={-1} ref={(el) => { questionRefs.current[index] = el; }}>
              <legend><span className="sa-question-number">{index + 1}.</span> {question}</legend>
              <div className="sa-options">
                {active.options.map((label, value) => <label className={answers[index] === value ? "selected" : ""} key={value}>
                  <input type="radio" name={`${active.id}-q${index + 1}`} value={value} checked={answers[index] === value}
                    onChange={() => { setAnswers((old) => old.map((a, i) => i === index ? value : a)); setError(""); }} />
                  <span>{label}</span>
                </label>)}
              </div>
            </fieldset>
            {index === active.safety_item_index && showSafety && <SafetySupport />}
          </div>)}
          {needsDifficulty && <fieldset className="sa-question" disabled={busy} tabIndex={-1} ref={difficultyRef}>
            <legend>{active.difficulty_question}</legend>
            <p className="sa-small">This question helps describe the impact on your life. It does not add to your score.</p>
            <div className="sa-options">{active.difficulty_options.map((label, value) => <label key={value} className={difficulty === value ? "selected" : ""}>
              <input type="radio" name="daily-life" value={value} checked={difficulty === value} onChange={() => { setDifficulty(value); setError(""); }} /><span>{label}</span>
            </label>)}</div>
          </fieldset>}
          <ScreeningNote />
          <p className="sa-small">{user ? "Submitting saves this assessment to your account."
            : "Your answers will be sent for scoring, but your guest result will not be saved."} Answers are not sent to the chat AI.</p>
          {error && <p className="sa-error" role="alert">{error}</p>}
          <button className="sa-primary" type="submit" disabled={busy}>
            {busy ? "Preparing your result…" : user ? "Submit and save my result" : "View my result"}<ArrowRight size={18} />
          </button>
        </form>
        <Sources source={active} />
      </>}

      {screen === "result" && result && <>
        <p className="sa-intro">Thank you for taking time to check in with yourself. Reaching out for support is a step you can take at any score.</p>
        {result.safety_followup && <SafetySupport />}
        <section className="sa-result">
          <div className="sa-result-meta"><strong>{result.title}</strong><span>{dateText(result.created_at)}</span></div>
          <p className="sa-score"><strong>{result.score}</strong><span> / {result.max_score}</span></p>
          <h3>{result.pss_reference?.band ?? result.band ?? "Perceived stress score"}</h3>
          <p>{result.pss_reference?.interpretation ?? result.interpretation}</p>
          {result.pss_reference && <>
            <ul className="sa-reference-bands" aria-label="PSS-10 reference ranges">
              {result.pss_reference.bands.map((band) => {
                const selected = result.score >= band.min && result.score <= band.max;
                return <li key={band.min} className={selected ? "is-current" : undefined}>
                  <strong>{band.min}–{band.max}</strong>
                  <span>{band.label}</span>
                  {selected && <small>Your range</small>}
                </li>;
              })}
            </ul>
            {result.pss_reference.applied_to_saved_result && <p className="sa-small">
              This saved score is shown using the current reference categories. Your original saved result has not been changed.
            </p>}
            <a className="sa-small" href={result.pss_reference.source_url} target="_blank" rel="noreferrer">
              About these reference categories <ExternalLink size={14} />
            </a>
          </>}
          {result.difficulty && <p className="sa-small">Impact on daily life: <strong>{result.difficulty}</strong> (not included in the score).</p>}
          <p className="sa-small">{result.saved ? "Saved to your account." : "Guest result — not saved. Refreshing, closing this page, or starting another assessment clears this result."}</p>
        </section>
        <section className="sa-next"><h3>What you can do next</h3><ul>{result.next_steps.map((step) => <li key={step}>{step}</li>)}</ul>
          <a href="https://care2caregivers.com/" target="_blank" rel="noreferrer">Explore Care2Caregivers support <ExternalLink size={15} /></a>
        </section>
        <ScreeningNote />
        <div className="sa-actions"><button className="sa-primary" onClick={() => setScreen("menu")}>Choose an assessment</button>
          {user && <button className="sa-secondary" onClick={openHistory}><History size={18} /> Saved results</button>}</div>
        <Sources source={result} />
      </>}

      {screen === "history" && <>
        <p className="sa-intro">Your most recent submitted assessments, with the date and result of each check-in.</p>
        {historyLoading && <p role="status">Loading saved results…</p>}
        {historyError && <div className="sa-error" role="alert">{historyError} <button onClick={openHistory}>Try again</button></div>}
        {!historyLoading && !historyError && (history.length ? <div className="sa-history">
          {history.map((item) => <button key={item.id} onClick={() => {
            if (dirty && !window.confirm("View this result? Your unfinished answers will not be saved.")) return;
            setActive(null); setAnswers([]); setResult(item); setScreen("result");
          }}>
            <span><strong>{item.title}</strong><small>{dateText(item.created_at)}</small></span>
            <span>{item.score} / {item.max_score} <ArrowRight size={18} /></span>
          </button>)}
        </div> : <p className="sa-note">You have no saved assessments yet. Choose a questionnaire to begin whenever you feel ready.</p>)}
        <ScreeningNote />
      </>}
      <p className="sa-help">Need immediate support in the U.S.? <a href="tel:988">Call 988</a> or <a href="sms:988">text 988</a>.
        In an emergency, <a href="tel:911">call 911</a>.</p>
  </div>;
}
