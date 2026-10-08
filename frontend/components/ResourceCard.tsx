import { Phone, Building2, PlayCircle, Clock, ExternalLink } from "lucide-react";
import type { ResourcesPayload } from "@/lib/api";

import { phoneHref } from "@/lib/phones";

export default function ResourceCard({
  resources,
}: {
  resources: ResourcesPayload;
}) {
  const { helplines, facilities, facilities_note, videos } = resources;

  return (
    <div className="resource-card">
      {helplines.length > 0 && (
        <div className="rc-section">
          <div className="rc-title">
            <Phone size={15} /> Helplines
          </div>
          {helplines.map((h) => (
            <div key={h.name} className="rc-item rc-helpline">
              <div className="rc-name">{h.name}</div>
              <div className="rc-actions">
                <a className="rc-phone" href={phoneHref(h.phone)} aria-label={`Call ${h.name}, ${h.phone}`}>
                  <Phone size={14} aria-hidden="true" /> {h.phone}
                </a>
                {h.url && (
                  <a className="rc-web" href={h.url} target="_blank" rel="noreferrer"
                    aria-label={`${h.name} website (opens in a new tab)`}>
                    Website <ExternalLink size={13} aria-hidden="true" />
                  </a>
                )}
              </div>
              {h.hours && (
                <div className="rc-hours"><Clock size={13} aria-hidden="true" /> {h.hours}</div>
              )}
              {h.after_hours && <div className="rc-after">{h.after_hours}</div>}
              <div className="rc-desc">{h.description}</div>
            </div>
          ))}
        </div>
      )}

      {facilities.length > 0 && (
        <div className="rc-section">
          <div className="rc-title">
            <Building2 size={15} /> NJ facilities · {facilities[0].county} County
          </div>
          {facilities.map((f) => (
            <div key={`${f.name}-${f.city}`} className="rc-item">
              <span className="rc-facility">{f.name}</span>
              <span className="rc-city"> — {f.city}</span>
            </div>
          ))}
          {facilities_note && <div className="rc-note">{facilities_note}</div>}
        </div>
      )}

      {videos.length > 0 && (
        <div className="rc-section">
          <div className="rc-title">
            <PlayCircle size={15} /> Related videos
          </div>
          {videos.map((v) => (
            <a
              key={v.url}
              className="rc-video"
              href={v.url}
              target="_blank"
              rel="noreferrer"
            >
              <PlayCircle size={15} /> {v.title}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
