"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChevronLeft, BarChart3, Smile, HeartHandshake } from "lucide-react";
import { getWellbeing, type WellbeingData } from "@/lib/api";

// Stress level (1-5) -> color: calm green -> warning amber -> high red.
function stressColor(level: number): string {
  if (level <= 2) return "#10b981";
  if (level === 3) return "#f59e0b";
  return "#ef4444";
}

const TREND_TEXT: Record<string, string> = {
  up: "and has been rising lately",
  down: "and has been easing lately",
  steady: "and has been fairly steady",
};

function summaryLine(d: WellbeingData): string {
  const s = d.summary;
  if (s.count === 0) return "";
  const level =
    (s.latest_stress ?? 0) >= 4
      ? "high"
      : (s.latest_stress ?? 0) === 3
        ? "moderate"
        : "low";
  return `You've checked in ${s.count} time${s.count > 1 ? "s" : ""}. Your recent stress is ${level} ${TREND_TEXT[s.trend]}.`;
}

export default function WellbeingView({
  sessionId,
  onBack,
}: {
  sessionId: string;
  onBack: () => void;
}) {
  const [data, setData] = useState<WellbeingData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    getWellbeing(sessionId)
      .then(setData)
      .catch(() => setError(true));
  }, [sessionId]);

  const points =
    data?.points.map((p, i) => ({
      idx: i + 1,
      stress: p.stress_level,
      when: new Date(p.ts * 1000).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      }),
    })) ?? [];

  const highStress = (data?.summary.latest_stress ?? 0) >= 4;

  return (
    <div className="app">
      <header className="header">
        <button className="ghost-btn" onClick={onBack} aria-label="Back to chat">
          <ChevronLeft size={22} />
        </button>
        <div>
          <h1>Your Well-being</h1>
          <div className="status" style={{ opacity: 0.9 }}>
            How you&apos;ve been feeling over time
          </div>
        </div>
      </header>

      <div className="wb-body">
        {error && <div className="empty">Couldn&apos;t load your trend right now.</div>}

        {data && data.summary.count === 0 && (
          <div className="empty">
            As you chat with I-Care, I&apos;ll gently keep track of how you&apos;re
            feeling and show it here.
          </div>
        )}

        {data && data.summary.count > 0 && (
          <>
            <p className="wb-summary">{summaryLine(data)}</p>

            <div className="wb-card">
              <div className="wb-card-title">
                <BarChart3 size={16} /> Stress over time (1–5)
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={points} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                  <XAxis dataKey="when" fontSize={11} tickLine={false} />
                  <YAxis domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} fontSize={11} />
                  <Tooltip
                    formatter={(v) => [`Stress: ${v}`, ""]}
                    labelFormatter={(l) => `${l}`}
                  />
                  <Bar dataKey="stress" radius={[4, 4, 0, 0]}>
                    {points.map((p, i) => (
                      <Cell key={i} fill={stressColor(p.stress)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {data.summary.top_emotions.length > 0 && (
              <div className="wb-card">
                <div className="wb-card-title">
                  <Smile size={16} /> What you&apos;ve been feeling
                </div>
                <div className="wb-emotions">
                  {data.summary.top_emotions.map(([emotion, n]) => (
                    <span key={emotion} className="wb-emotion-chip">
                      {emotion} · {n}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {highStress && (
              <div className="wb-care">
                <HeartHandshake size={20} />
                <div>
                  It looks like this has been a heavy stretch. Please be gentle
                  with yourself — you matter too. You can reach the Care2Caregivers
                  helpline anytime at <strong>1-800-424-2494</strong>, and ask me
                  for &ldquo;self-care tips&rdquo; whenever you need them.
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <footer className="footer">
        ©2026 Rutgers, The State University of New Jersey, All rights reserved. Do
        not copy or reproduce without permission.
      </footer>
    </div>
  );
}
