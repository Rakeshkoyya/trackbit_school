import type { Metadata } from "next";
import Link from "next/link";
import { Bricolage_Grotesque } from "next/font/google";

import { RedirectIfAuthed } from "@/components/auth/redirect-if-authed";
import { DayBoard } from "@/components/marketing/day-board";
import { DemoForm } from "@/components/marketing/demo-form";
import { PricingCalculator } from "@/components/marketing/pricing-calculator";

import "./marketing.css";

// The display face. Bricolage's optical-size axis lets the headline set tight
// and dense at hero scale — a timetable header, not a hero banner.
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "TrackBit School — the school's daily operating system",
  description:
    "AI-native software for schools of 500+ students. Plan the academic year down to the period, capture every class in one tap, track each student's growth subject by subject, and get the daily report written for you. ₹100 per student per month.",
};

const facts = [
  { n: "8", l: "periods a day, each one on the record — not a monthly summary" },
  { n: "≤5", l: "taps for a teacher to close a period, attendance included" },
  { n: "0", l: "reports anyone has to write. The 8 AM report writes itself" },
  { n: "1", l: "system for planning, classrooms, hostel, tasks and fees" },
];

const modules = [
  {
    tag: "Pillar 01",
    title: "Student growth",
    body: "Every student, subject by subject: what was taught, what they were present for, what they scored, and where they are slipping.",
    points: [
      "Chapter-level view, drill down to a single topic",
      "Topics missed while absent, listed by name",
      "Test scores, skill profile and growth areas",
      "Private A/B/C tiers for staff — never a label a parent sees",
    ],
  },
  {
    tag: "Pillar 02",
    title: "Academic planner",
    body: "The year's syllabus is compiled into a period-by-period plan, then held to it. The plan is the baseline; the classroom log is the actual.",
    points: [
      "Term-scoped chapters sized to real teaching days",
      "Red / amber / green pace forecast per class-subject",
      "Approved plans lock — re-forecast never rewrites them",
      "Exam-fit check: is the portion finishable before the test?",
    ],
  },
  {
    tag: "Pillar 03",
    title: "Teacher tracking",
    body: "Not surveillance — visibility. You can see which periods were held, what was covered, and where a class has quietly fallen behind.",
    points: [
      "Timetable with clash detection, imported from your file",
      "Per-period attendance, topic covered and homework set",
      "Optional deep log: flag only the students who deviate",
      "Unmarked periods chase the teacher, not you",
    ],
  },
  {
    tag: "Module",
    title: "Tasks & boards",
    body: "The school's non-academic work — maintenance, housekeeping, events — on boards anyone can pick up.",
    points: [
      "Assign it, or leave it claimable",
      "Recurring routines materialise themselves",
      "Every dashboard alert becomes a task in one tap",
    ],
  },
  {
    tag: "Module",
    title: "Fees",
    body: "Structures, instalments, discounts and receipts, on a ledger that is appended to and never edited.",
    points: [
      "Per-class fee structures and instalment plans",
      "Payment, undo and discount as compensating entries",
      "Director-only: teachers never see a rupee",
    ],
  },
  {
    tag: "Module",
    title: "Hostel & sessions",
    body: "Evening prep, study blocks and activities run on the same rails as the school day, for the students who never go home.",
    points: [
      "Rosters compute themselves from class + hosteller category",
      "Study, homework and activity blocks, each with its own capture",
      "Photos and video attach to the session, never to a child",
    ],
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
            <p className="mk-eyebrow">AI-native school operating system</p>
            <h1 className="mk-h1 mk-display">
              Every period of every day, <em>on the record.</em>
            </h1>
            <p className="mk-lead">
              TrackBit School plans your academic year down to the period, captures each class in a
              tap, and turns it into per-student growth subject by subject. Then it writes the
              day&apos;s report itself — and keeps growing into how your school actually works.
            </p>
            <div className="mk-cta-row">
              <a className="mk-btn mk-btn-primary" href="#demo">
                Book a demo
              </a>
              <a className="mk-btn mk-btn-ghost" href="#pricing">
                See pricing
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

      {/* ── What it tracks ──────────────────────────────────────────────── */}
      <section className="mk-section mk-shell" id="product">
        <div className="mk-section-head">
          <p className="mk-eyebrow">What it tracks</p>
          <h2 className="mk-h2 mk-display">
            Three things a head of school can never see clearly — and the running of the place.
          </h2>
          <p className="mk-sub">
            Student growth, the academic plan and the teaching itself are the pillars. Tasks, fees
            and hostel sit on the same data, so nothing is ever entered twice.
          </p>
        </div>

        <div className="mk-modules">
          {modules.map((m) => (
            <article key={m.title} className="mk-module">
              <p className="mk-module-tag mk-mono">{m.tag}</p>
              <h3>{m.title}</h3>
              <p>{m.body}</p>
              <ul>
                {m.points.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      {/* ── The loop ────────────────────────────────────────────────────── */}
      <section className="mk-section mk-shell">
        <div className="mk-section-head">
          <p className="mk-eyebrow">The daily loop</p>
          <h2 className="mk-h2 mk-display">Nobody writes a report. It falls out of the work.</h2>
          <p className="mk-sub">
            Every number in TrackBit is a byproduct of a teacher doing their job, captured in the
            moment with a tap. There is no separate data-entry job — a system that needs one gets
            abandoned by March.
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

      {/* ── AI ──────────────────────────────────────────────────────────── */}
      <section className="mk-section mk-shell">
        <div className="mk-section-head">
          <p className="mk-eyebrow">The AI layer</p>
          <h2 className="mk-h2 mk-display">It evolves with your school, not against it.</h2>
          <p className="mk-sub">
            AI here is plumbing, not a gimmick. It reads the timetable photo you send, splits a
            chapter into teachable topics, drafts the daily report, and answers questions about your
            own school in plain language. A person confirms everything before it is saved.
          </p>
        </div>

        <div className="mk-ai">
          <div className="mk-ai-copy">
            <p className="mk-eyebrow">Ask Lucy</p>
            <h3>Your school, queried in a sentence.</h3>
            <p>
              Staff ask in plain English and get an answer built from live data, never a guess. Lucy
              reads through the same permissions you have, so a teacher sees their classes and a
              director sees the school. Anything that changes data waits for your confirmation.
            </p>
            <p>
              And it starts where your school already is. Adopting mid-term, sizing chapters as they
              come, running a hostel alongside the school — the system bends to that instead of
              asking you to start the year again.
            </p>
          </div>

          <div className="mk-ai-demo">
            <p className="mk-ask">
              &ldquo;Which classes are behind on Science before the half-yearly?&rdquo;
            </p>
            <p className="mk-answer">Three of eight, measured against the approved plan:</p>
            <div className="mk-answer-rows mk-mono">
              <div className="mk-answer-row">
                <span>8B · Science</span>
                <span>
                  <b>6 periods</b> behind · 4 topics left
                </span>
              </div>
              <div className="mk-answer-row">
                <span>7A · Science</span>
                <span>
                  <b>4 periods</b> behind · 3 topics left
                </span>
              </div>
              <div className="mk-answer-row">
                <span>9C · Science</span>
                <span>
                  <b>2 periods</b> behind · 1 topic left
                </span>
              </div>
            </div>
            <p className="mk-answer">
              The other five finish the portion with days to spare. Want this as a task for the
              Science coordinator?
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
            There is no free tier and no trial you have to configure yourself. You pay, we build
            your school inside TrackBit from the files you already have, and hand it over working.
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
              <li>Guardian notifications on WhatsApp</li>
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
