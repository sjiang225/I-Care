"use client";

import { Brain, Moon, MapPin, Users, MessageCircle, ArrowRight, Phone } from "lucide-react";

const TOPICS = [
  { icon: Brain, label: "Managing challenging behaviors", text: "How can I manage challenging behaviors such as agitation or aggression?" },
  { icon: Moon, label: "Sleep problems", text: "The person I care for has trouble sleeping at night. What can I do?" },
  { icon: MapPin, label: "Find care options", text: "What care options are available for the person I care for in New Jersey?" },
  { icon: Users, label: "Someone to talk to", text: "I'm feeling overwhelmed and need someone to talk to." },
];

export default function HomeView({ hasConversation, hasDraft, sending, onChat, onAssessment, onLibrary, onTopic, onHelp }: {
  hasConversation: boolean;
  hasDraft: boolean;
  sending: boolean;
  onChat: () => void;
  onAssessment: () => void;
  onLibrary: () => void;
  onTopic: (text: string) => void;
  onHelp: () => void;
}) {
  const resume = hasConversation || hasDraft;
  return <div className="home-inner">
    <div className="home-hero">
      <div className="home-hero-copy">
        <p className="home-eyebrow">Dementia caregiver support</p>
        <h2 id="home-heading" tabIndex={-1}>How can I support you today?</h2>
        <p className="home-lede">Reliable guidance from trusted caregiving resources, and a caring space to talk things through.</p>
        <div className="home-cta">
          <button className="home-primary" onClick={onChat}>
            <MessageCircle size={22} aria-hidden="true" />
            {resume ? "Continue chatting" : "Start chatting"}
            <ArrowRight size={20} aria-hidden="true" />
          </button>
          <button className="home-secondary" onClick={onAssessment}>
            Self-assessment <ArrowRight size={20} aria-hidden="true" />
          </button>
        </div>
        {sending && <p className="home-status" role="status">Your reply is being prepared in Chat.</p>}
        <button className="home-guide-link" onClick={onHelp} aria-haspopup="dialog">New to I-Care? See how it works</button>
      </div>
      <img className="home-hero-art" src="/home-hero.jpg" alt="" width={732} height={598} />
    </div>


    <section className="home-topics" aria-labelledby="home-topics-heading">
      <div className="home-topics-head">
        <h3 id="home-topics-heading">Topics caregivers often ask about</h3>
        <p>Choose a topic to begin a conversation.</p>
        <button className="home-library-link" onClick={onLibrary}>
          Browse Library <ArrowRight size={17} aria-hidden="true" />
        </button>
      </div>
      <div className="home-topic-list">
        {TOPICS.map((topic) => <button key={topic.label} className="home-topic" onClick={() => onTopic(topic.text)} disabled={sending}>
          <topic.icon size={30} strokeWidth={1.6} aria-hidden="true" />
          <span>{topic.label}</span>
          <ArrowRight size={18} aria-hidden="true" />
        </button>)}
      </div>
    </section>

    {/* R09: always on Home, deliberately calm (not role="alert") so it never interrupts. */}
    <section className="home-urgent" aria-labelledby="home-urgent-title">
      <h3 id="home-urgent-title"><Phone size={26} strokeWidth={1.8} aria-hidden="true" /> Urgent help</h3>
      <div className="home-urgent-item">
        <span className="home-urgent-label">Immediate danger</span>
        <a className="home-urgent-call" href="tel:911" aria-label="Call 911"><Phone size={17} aria-hidden="true" /> Call 911</a>
      </div>
      <div className="home-urgent-item">
        <span className="home-urgent-label">Emotional crisis<small>24/7</small></span>
        <a className="home-urgent-call" href="tel:988" aria-label="Call or text 988, 24/7"><Phone size={17} aria-hidden="true" /> Call or text 988</a>
      </div>
    </section>

    <footer className="home-footer">
      <p className="home-disclaimer">I-Care is an educational tool, not medical advice.</p>
      <p className="home-funding">This project has been funded by a grant from <strong>New Jersey Health Foundation.</strong></p>
      <p>©2026 Rutgers, The State University of New Jersey. All rights reserved.</p>
    </footer>
  </div>;
}
