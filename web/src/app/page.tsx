import type { Metadata } from "next";
import Link from "next/link";
import { Bricolage_Grotesque } from "next/font/google";

import { RedirectIfAuthed } from "@/components/auth/redirect-if-authed";
import { DayBoard } from "@/components/marketing/day-board";
import { DemoForm } from "@/components/marketing/demo-form";
import { DirectorDashboard } from "@/components/marketing/director-dashboard";
import { GenerativeBuild } from "@/components/marketing/generative-build";
import { GrowthTracker } from "@/components/marketing/growth-tracker";
import { LucyPeek } from "@/components/marketing/lucy-peek";
import { ParentPortal } from "@/components/marketing/parent-portal";
import { PeriodCard } from "@/components/marketing/period-card";
import { PricingCalculator } from "@/components/marketing/pricing-calculator";
import { ReportWriter } from "@/components/marketing/report-writer";

import "./marketing.css";

// The display face. Bricolage's optical-size axis lets the headline set tight
// and dense at hero scale — a timetable header, not a hero banner.
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "TrackBit School — see every classroom, every day",
  description:
    "You run a school of hundreds of students and dozens of teachers — and can't see what actually happened in class today. TrackBit puts every period on the record in one tap, tracks each student's growth subject by subject, writes the daily report itself, and lets parents log in to their child's day. ₹100 per student per month.",
};

const facts = [
  { n: "8", l: "periods a day, each one on the record — not a monthly summary" },
  { n: "≤5", l: "taps for a teacher to close a period, attendance included" },
  { n: "0", l: "reports anyone has to write. The 8 AM report writes itself" },
  { n: "1", l: "system for planning, classrooms, growth, parents and fees" },
];

const personas = [
  {
    who: "The director",
    pain: "You can't see what's really happening. The monthly summary is written after the fact — and everyone knows it.",
    fix: "A live view of every classroom, and a report waiting at 8 AM.",
  },
  {
    who: "The teacher",
    pain: "You have no time for software. The same attendance and homework, written into a register, a diary and a WhatsApp group.",
    fix: "One tap closes a period. Recording it is the whole job.",
  },
  {
    who: "The parent",
    pain: "You're the last to know. A call to the office, and still no clear answer about your child's day.",
    fix: "Log in and see the day yourself — what was taught, and what your child missed.",
  },
];

const loop = [
  {
    n: "Step 1",
    title: "We compile your year",
    body: "You hand over your syllabus, staff list and roster. We import them and generate a plan for every class-subject, down to the period.",
  },
  {
    n: "Step 2",
    title: "Teachers confirm by exception",
    body: "The norm is one tap: class present, topic covered. Teachers only enter the deviations — who was absent, what didn't get done.",
  },
  {
    n: "Step 3",
    title: "It joins into per-student truth",
    body: "Timetable × attendance × topics × homework × scores. Nobody enters this; it is a computed join of work already done.",
    active: true,
  },
  {
    n: "Step 4",
    title: "The report arrives at 8 AM",
    body: "Risks, ambiguities and wins, written overnight — plus one-tap tasks for anything that needs a person.",
  },
];

type ShowcaseProps = {
  id?: string;
  eyebrow: string;
  title: React.ReactNode;
  sub: string;
  media: React.ReactNode;
  flip?: boolean;
};

function Showcase({ id, eyebrow, title, sub, media, flip }: ShowcaseProps) {
  return (
    <section className="mk-section mk-shell" id={id}>
      <div className="mk-show" data-flip={flip ? "true" : "false"}>
        <div className="mk-show-copy">
          <p className="mk-eyebrow">{eyebrow}</p>
          <h2 className="mk-h2 mk-display">{title}</h2>
          <p className="mk-sub">{sub}</p>
        </div>
        <div className="mk-show-media">{media}</div>
      </div>
    </section>
  );
}

export default function LandingPage() {
  return (
    <div className={`mk ${display.variable}`}>
      <RedirectIfAuthed />

      <header className="mk-shell">
        <nav className="mk-nav">
          <Link
            href="/"
            className="mk-wordmark"
            style={{ color: "var(--mk-chalk)", textDecoration: "none" }}
          >
            TrackBit <span>School</span>
          </Link>
          <div className="mk-navlinks">
            <a className="mk-navlink" href="#product" data-optional="true">
              Product
            </a>
            <a className="mk-navlink" href="#pricing" data-optional="true">
              Pricing
            </a>
            <Link className="mk-navlink" href="/auth/login">
              Sign in
            </Link>
            <a className="mk-btn mk-btn-primary mk-btn-sm" href="#demo">
              Book a demo
            </a>
          </div>
        </nav>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <section className="mk-hero">
        <div className="mk-shell mk-hero-grid">
          <div>
            <p className="mk-eyebrow">The school&apos;s daily operating system</p>
            <p className="mk-hero-kicker">
              You have 40 teachers and 800 students. Right now, no one can tell you what actually
              happened in class today.
            </p>
            <h1 className="mk-h1 mk-display">
              Every period of every day, <em>on the record.</em>
            </h1>
            <p className="mk-lead">
              TrackBit plans your year down to the period, captures each class in one tap, and turns
              it into per-student growth subject by subject. Then it writes the day&apos;s report
              itself — and asks your teachers for no data entry, so it&apos;s still running in March.
            </p>
            <div className="mk-cta-row">
              <a className="mk-btn mk-btn-primary" href="#demo">
                Book a demo
              </a>
              <a className="mk-btn mk-btn-ghost" href="#product">
                See how it works
              </a>
            </div>
            <p className="mk-hero-note mk-mono">
              <b>₹100</b> per student, per month · minimum 500 students · we set it up for you
            </p>
          </div>

          <DayBoard />
        </div>
      </section>

      {/* ── Facts ───────────────────────────────────────────────────────── */}
      <section className="mk-facts">
        <div className="mk-shell">
          <div className="mk-facts-grid">
            {facts.map((f) => (
              <div key={f.l} className="mk-fact">
                <p className="mk-fact-n">{f.n}</p>
                <p className="mk-fact-l">{f.l}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Personas ────────────────────────────────────────────────────── */}
      <section className="mk-section mk-shell" id="product">
        <div className="mk-section-head">
          <p className="mk-eyebrow">The problem</p>
          <h2 className="mk-h2 mk-display">Three people. Three problems. One system.</h2>
          <p className="mk-sub">
            A school runs on things nobody can quite see: whether the class was taught, whether the
            teacher had a minute to log it, whether the parent ever found out. TrackBit is built for
            all three at once.
          </p>
        </div>

        <div className="mk-persona-grid">
          {personas.map((p) => (
            <article key={p.who} className="mk-persona">
              <p className="mk-persona-who mk-display">{p.who}</p>
              <p className="mk-persona-pain">{p.pain}</p>
              <p className="mk-persona-fix">
                <span className="mk-persona-arrow mk-mono">→</span> {p.fix}
              </p>
            </article>
          ))}
        </div>
      </section>

      {/* ── Director's dashboards ───────────────────────────────────────── */}
      <Showcase
        eyebrow="For the director"
        title="The morning you stop chasing people."
        sub="Open the dashboard and the whole school is in front of you: the syllabus pace of every class-subject, the numbers that matter, and the short list of things that actually need you. Every alert becomes a task in one tap."
        media={<DirectorDashboard />}
      />

      {/* ── Capture by exception ────────────────────────────────────────── */}
      <Showcase
        flip
        eyebrow="For the teacher"
        title="One tap. That is the entire job."
        sub="The norm is one tap — class present, topic covered. Teachers record only the exceptions: who was away, what didn't get done. A full period on the record in four taps, under half a minute. That is why they keep using it past March."
        media={<PeriodCard />}
      />

      {/* ── Growth tracker ──────────────────────────────────────────────── */}
      <Showcase
        eyebrow="Every student"
        title="Growth you can actually follow — subject by subject."
        sub="For any child: how much of each subject has really been taught, the topics they missed while absent, their test trend, and where they need help. Built from the day's captures, so it is never out of date."
        media={<GrowthTracker />}
      />

      {/* ── Report writes itself ────────────────────────────────────────── */}
      <Showcase
        flip
        eyebrow="The 8 AM report"
        title="Nobody writes it. It writes itself."
        sub="Overnight, TrackBit reads the day — attendance, topics, homework, pace, fees — and composes the report: the risks, the loose ends, the wins. It is on your phone before the first bell, every day."
        media={<ReportWriter />}
      />

      {/* ── Parent portal ───────────────────────────────────────────────── */}
      <Showcase
        eyebrow="For parents"
        title="Parents stop calling the office. They just log in."
        sub="Every parent gets a login to their child's day: the topic taught in each period, the homework set, and — when their child was absent — exactly what they missed. The class record, in the open. The private A/B/C tiers staff use for intervention are never shown to a parent."
        media={<ParentPortal />}
      />

      {/* ── The loop ────────────────────────────────────────────────────── */}
      <section className="mk-section mk-shell">
        <div className="mk-section-head">
          <p className="mk-eyebrow">The daily loop</p>
          <h2 className="mk-h2 mk-display">Every number is a byproduct of the work.</h2>
          <p className="mk-sub">
            Nothing on this page is a separate data-entry job. Each figure falls out of a teacher
            doing their job, captured in the moment with a tap — which is the only reason a school
            keeps using it.
          </p>
        </div>

        <div className="mk-loop">
          {loop.map((s) => (
            <div key={s.title} className="mk-step" data-active={s.active ? "true" : "false"}>
              <p className="mk-step-n mk-mono">{s.n}</p>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── AI layer ────────────────────────────────────────────────────── */}
      <section className="mk-section mk-shell">
        <div className="mk-section-head">
          <p className="mk-eyebrow">The AI layer</p>
          <h2 className="mk-h2 mk-display">A platform that evolves with your school.</h2>
          <p className="mk-sub">
            AI here is plumbing, not a gimmick — it reads your timetable photo, splits a chapter into
            topics, drafts the daily report, and answers questions in plain language. A person
            confirms anything that changes data. And it is heading somewhere: a school system that
            reshapes itself to how you actually work.
          </p>
        </div>

        <div className="mk-ai-two">
          <div className="mk-ai-item">
            <GenerativeBuild />
            <p className="mk-ai-cap">
              <b>The direction we&apos;re building.</b> Describe a tracker in plain words and watch
              the module take shape — a school OS that grows new views on demand.
            </p>
          </div>
          <div className="mk-ai-item">
            <LucyPeek />
            <p className="mk-ai-cap">
              <b>Shipped today: ask Lucy.</b> Staff query the school in plain English and get an
              answer from live data, through their own permissions — never a guess.
            </p>
          </div>
        </div>
      </section>

      {/* ── Pricing ─────────────────────────────────────────────────────── */}
      <section className="mk-section mk-shell" id="pricing">
        <div className="mk-section-head">
          <p className="mk-eyebrow">Pricing</p>
          <h2 className="mk-h2 mk-display">One price, per student. That is the whole model.</h2>
          <p className="mk-sub">
            There is no free tier and no trial you have to configure yourself. You pay, we build your
            school inside TrackBit from the files you already have, and hand it over working.
          </p>
        </div>

        <div className="mk-price">
          <div className="mk-price-main">
            <p className="mk-eyebrow">The only plan</p>
            <div className="mk-price-rate">
              <strong>₹100</strong>
              <span>per student, per month</span>
            </div>
            <p className="mk-price-min mk-mono">Minimum 500 students per school</p>

            <ul className="mk-includes">
              <li>Every module — no editions, no add-ons</li>
              <li>Setup done by us, from your files</li>
              <li>Syllabus, roster and staff import</li>
              <li>Timetable built and validated</li>
              <li>Plans generated and approved with you</li>
              <li>Staff training and handover</li>
              <li>Unlimited teacher and admin accounts</li>
              <li>Parent portal — a login for every parent</li>
            </ul>
          </div>

          <PricingCalculator />
        </div>
      </section>

      {/* ── Demo ────────────────────────────────────────────────────────── */}
      <section className="mk-demo" id="demo">
        <div className="mk-shell mk-demo-grid">
          <div>
            <p className="mk-eyebrow">Book a demo</p>
            <h2 className="mk-h2 mk-display">See your own school in it.</h2>
            <p className="mk-sub">
              Send your details and we will walk you through TrackBit on your classes, your subjects
              and your calendar — not a sample school.
            </p>
            <ul className="mk-checklist">
              <li>
                <b>01</b> A 30-minute call to understand how your school runs today
              </li>
              <li>
                <b>02</b> We load a slice of your real data and show you the day board
              </li>
              <li>
                <b>03</b> A written quote based on your roll, and a setup date
              </li>
            </ul>
          </div>

          <DemoForm />
        </div>
      </section>

      <footer className="mk-footer">
        <div className="mk-shell mk-footer-in">
          <p>{`© ${new Date().getFullYear()} TrackBit School · The school's daily operating system`}</p>
          <p>
            <Link href="/auth/login">Sign in</Link> · <a href="#demo">Book a demo</a>
          </p>
        </div>
      </footer>
    </div>
  );
}
