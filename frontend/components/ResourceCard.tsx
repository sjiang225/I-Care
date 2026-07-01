import { Phone, Building2, PlayCircle } from "lucide-react";
import type { ResourcesPayload } from "@/lib/api";

function telHref(phone: string): string {
  return "tel:" + phone.replace(/[^0-9]/g, "");
}

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
            <div key={h.name} className="rc-item">
              <a className="rc-phone" href={telHref(h.phone)}>
                <Phone size={13} /> {h.name} · {h.phone}
              </a>
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
