// Thin wrappers over the browser Web Speech API (free, no native code).
// Speech-to-text (dictation) + text-to-speech (read answers aloud).
// English-only for the first version (see DESIGN.md decision #3).

/* eslint-disable @typescript-eslint/no-explicit-any */

export function speechSupported(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(
    (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  );
}

export function ttsSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export interface Dictation {
  stop: () => void;
}

// Start dictation; calls onResult with the (interim/final) transcript.
export function startDictation(
  onResult: (text: string, isFinal: boolean) => void,
  onEnd: () => void
): Dictation | null {
  const Ctor =
    (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!Ctor) return null;

  const recog = new Ctor();
  recog.lang = "en-US";
  recog.interimResults = true;
  recog.continuous = false;

  recog.onresult = (event: any) => {
    let transcript = "";
    let isFinal = false;
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
      if (event.results[i].isFinal) isFinal = true;
    }
    onResult(transcript, isFinal);
  };
  recog.onerror = () => onEnd();
  recog.onend = () => onEnd();
  recog.start();

  return { stop: () => recog.stop() };
}

export function speak(text: string): void {
  if (!ttsSupported()) return;
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "en-US";
  utter.rate = 0.95;
  window.speechSynthesis.speak(utter);
}

export function stopSpeaking(): void {
  if (ttsSupported()) window.speechSynthesis.cancel();
}
