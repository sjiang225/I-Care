"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { BookOpen, ExternalLink, PlayCircle, Search } from "lucide-react";
import { sourceHref } from "@/lib/citations";

type Guide = { id: string; title: string; category: string; url: string | null };
type Video = Guide & { language: string };
type ResourceType = "all" | "guide" | "video";
type Resource = Guide & { kind: "guide" | "video"; language: string };
type Catalogue = { documents: Guide[]; videos: Video[]; categories: { id: string; label: string }[] };
const LANGUAGE_LABELS: Record<string, string> = { en: "English", es: "Spanish", ru: "Russian" };
const RESOURCE_TYPES = [
  { id: "all", label: "All" }, { id: "guide", label: "Guides" }, { id: "video", label: "Videos" },
] as const;

export default function GuideLibrary({ visible }: { visible: boolean }) {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [resourceType, setResourceType] = useState<ResourceType>("all");
  const bodyRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const scrollRef = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(false);
    fetch("/api/library", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Catalogue unavailable");
        return response.json() as Promise<Catalogue>;
      })
      .then(setCatalogue)
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [attempt]);

  useLayoutEffect(() => {
    if (visible) {
      if (bodyRef.current) bodyRef.current.scrollTop = scrollRef.current;
      headingRef.current?.focus({ preventScroll: true });
    }
  }, [visible]);

  const resources: Resource[] = catalogue ? [
    ...catalogue.documents.map((guide): Resource => ({ ...guide, kind: "guide", language: "en" })),
    ...(catalogue.videos ?? []).map((video): Resource => ({ ...video, kind: "video" })),
  ] : [];
  const totals = {
    all: resources.length,
    guide: catalogue?.documents.length ?? 0,
    video: catalogue?.videos?.length ?? 0,
  };
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const groups = catalogue?.categories.map((topic) => ({
    ...topic,
    resources: resources.filter((item) => {
      const haystack = `${item.title} ${topic.label} ${LANGUAGE_LABELS[item.language] ?? item.language}`.toLocaleLowerCase();
      return item.category === topic.id && (category === "all" || category === topic.id)
        && (resourceType === "all" || resourceType === item.kind)
        && terms.every((term) => haystack.includes(term));
    }),
  })).filter((group) => group.resources.length) ?? [];
  const count = groups.reduce((total, group) => total + group.resources.length, 0);
  const filtered = Boolean(query.trim()) || category !== "all" || resourceType !== "all";
  const resultLabel = resourceType === "guide" ? "guides" : resourceType === "video" ? "videos" : "resources";

  return <div className="library-body" ref={bodyRef}
    onScroll={(event) => { if (visible) scrollRef.current = event.currentTarget.scrollTop; }}>
    <p className="library-eyebrow"><BookOpen size={17} aria-hidden="true" /> Care2Caregivers resources</p>
    <h2 id="library-heading" ref={headingRef} tabIndex={-1}>Guides &amp; videos</h2>
    <p className="library-intro">Read a guide or watch a video. No question needed.</p>
    <p className="library-note">PDFs and YouTube videos open in a new tab.</p>

    {!catalogue && !error && <p role="status" className="library-state">Loading resources…</p>}
    {error && <div className="library-state library-error" role="alert">
      <p>We couldn&apos;t load the resources. Please try again.</p>
      <button onClick={() => setAttempt((value) => value + 1)}>Try again</button>
    </div>}
    {catalogue && <>
      <div className="library-types" role="group" aria-label="Resource type">
        {RESOURCE_TYPES.map((type) => <button key={type.id} aria-pressed={resourceType === type.id}
          onClick={() => setResourceType(type.id)}>
          {type.label}<span>{totals[type.id]}</span>
        </button>)}
      </div>
      <div className="library-filters">
        <div><label htmlFor="guide-search">Search resources</label>
          <div className="library-search"><Search size={19} aria-hidden="true" />
            <input id="guide-search" type="search" placeholder="Try sleep, care or communication" value={query}
              onChange={(event) => setQuery(event.target.value)} />
          </div>
        </div>
        <div><label htmlFor="guide-topic">Filter by topic</label>
          <select id="guide-topic" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="all">All topics</option>
            {catalogue.categories.map((topic) => <option key={topic.id} value={topic.id}>{topic.label}</option>)}
          </select>
        </div>
      </div>
      <div className="library-results-bar">
        <p role="status" aria-atomic="true">{filtered ? `${count} of ${totals[resourceType]} ${resultLabel}` : `${count} resources · ${catalogue.categories.length} topics`}</p>
        {filtered && <button onClick={() => { setQuery(""); setCategory("all"); setResourceType("all"); }}>Clear filters</button>}
      </div>
      {!count && <div className="library-state">
        <h3>No resources found</h3><p>Try another search or clear the filters to see all guides and videos.</p>
      </div>}
      <div className="library-groups">
        {groups.map((group) => <section key={group.id} className="library-group" aria-labelledby={`guide-topic-${group.id}`}>
          <h3 id={`guide-topic-${group.id}`}>{group.label}<span>{group.resources.length}</span></h3>
          <ul>{group.resources.map((item) => {
            const href = sourceHref(item.url);
            const isVideo = item.kind === "video";
            const language = LANGUAGE_LABELS[item.language] ?? item.language;
            const Icon = isVideo ? PlayCircle : BookOpen;
            return <li key={`${item.kind}:${item.id}`}>
              {href ? <a className="guide-link" href={href} target="_blank" rel="noreferrer"
                aria-label={`${item.title} — ${language} — ${isVideo ? "watch on YouTube" : "open PDF"} in a new tab`}>
                <span className={`guide-file-icon${isVideo ? " video-file-icon" : ""}`}><Icon size={20} aria-hidden="true" /></span>
                <span className="guide-copy"><strong>{item.title}</strong>
                  <span>{isVideo ? "Watch video · YouTube" : "Read guide · PDF"} · {language}</span></span>
                <ExternalLink size={17} aria-hidden="true" />
              </a> : <div className="guide-link guide-unavailable"><span className="guide-copy"><strong>{item.title}</strong><span>{isVideo ? "Video" : "PDF"} · {language} · Link currently unavailable</span></span></div>}
            </li>;
          })}</ul>
        </section>)}
      </div>
    </>}
    <div className="library-publisher"><p>More from Care2Caregivers / Rutgers Health:</p>
      <a href="https://care2caregivers.com/help-for-caregivers/educational-guides-and-brochures/"
        target="_blank" rel="noreferrer">Educational guides <ExternalLink size={13} aria-hidden="true" /><span className="sr-only"> (opens in a new tab)</span></a>
      <a href="https://care2caregivers.com/help-for-caregivers/videos/"
        target="_blank" rel="noreferrer">Caregiver videos <ExternalLink size={13} aria-hidden="true" /><span className="sr-only"> (opens in a new tab)</span></a>
    </div>
  </div>;
}
