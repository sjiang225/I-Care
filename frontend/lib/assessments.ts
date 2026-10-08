import { authHeaders } from "./auth";

export interface Instrument {
  id: "phq9" | "gad7" | "pss10";
  version: string;
  name: string;
  title: string;
  description: string;
  recall: string;
  instructions: string;
  questions: string[];
  options: string[];
  max_score: number;
  difficulty_question: string | null;
  difficulty_options: string[];
  safety_item_index: number | null;
  source_pdf: string;
  source_url: string;
  attribution: string;
}

export interface AssessmentResult {
  id: number | null;
  instrument_id: Instrument["id"];
  instrument_version: string;
  title: string;
  score: number;
  max_score: number;
  band: string | null;
  pss_reference?: {
    band: string;
    bands: { min: number; max: number; label: string }[];
    interpretation: string;
    source_url: string;
    applied_to_saved_result: boolean;
  };
  interpretation: string;
  next_steps: string[];
  safety_followup: boolean;
  difficulty: string | null;
  created_at: number;
  saved: boolean;
  source_pdf: string;
  source_url: string;
  attribution: string;
}

async function readResponse<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Please check your answers and try again.");
  }
  return data;
}

export async function getInstruments(signal?: AbortSignal): Promise<Instrument[]> {
  const data = await readResponse<{ instruments: Instrument[] }>(await fetch(
    "/api/assessments/instruments", { signal, cache: "no-store" },
  ));
  return data.instruments;
}

export async function submitAssessment(input: {
  instrument_id: Instrument["id"];
  instrument_version: string;
  answers: number[];
  difficulty: number | null;
  submission_id: string;
  save: boolean;
}): Promise<AssessmentResult> {
  return readResponse(await fetch("/api/assessments", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
    cache: "no-store",
  }));
}

export async function getAssessmentHistory(): Promise<AssessmentResult[]> {
  const data = await readResponse<{ results: AssessmentResult[] }>(await fetch(
    "/api/assessments/history", { headers: authHeaders(), cache: "no-store" },
  ));
  return data.results;
}
