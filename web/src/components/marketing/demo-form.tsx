"use client";

import { useState } from "react";
import { Check } from "lucide-react";

import { marketingApi } from "@/lib/marketing-api";

/**
 * Book a demo. Posts to the one public endpoint; the row lands in
 * `demo_requests` for the operator to work through.
 */

type Status = "idle" | "sending" | "done";

const EMPTY = {
  school_name: "",
  contact_name: "",
  email: "",
  phone: "",
  city: "",
  student_count: "",
  message: "",
};

export function DemoForm() {
  const [form, setForm] = useState(EMPTY);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus("sending");
    try {
      const count = form.student_count.trim();
      await marketingApi.bookDemo({
        school_name: form.school_name.trim(),
        contact_name: form.contact_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        city: form.city.trim() || null,
        student_count: count ? Number(count) : null,
        message: form.message.trim() || null,
        source: "landing",
      });
      setStatus("done");
    } catch (err) {
      setStatus("idle");
      setError(
        err instanceof Error
          ? err.message
          : "That didn't go through. Try again, or write to hello@trackbit.in.",
      );
    }
  }

  if (status === "done") {
    return (
      <div className="mk-form">
        <div className="mk-done">
          <div className="mk-done-mark">
            <Check className="h-5 w-5" strokeWidth={2.5} />
          </div>
          <h3 className="mk-display">Booked. We&apos;ll call you.</h3>
          <p>
            We read every request the same day and call within one working day to fix a time. The
            demo runs on your own classes and subjects, not a sample school.
          </p>
        </div>
      </div>
    );
  }

  return (
    <form className="mk-form" onSubmit={submit} noValidate={false}>
      {error ? (
        <p className="mk-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="mk-fields">
        <div className="mk-field" data-wide="true">
          <label htmlFor="mk-school">School name</label>
          <input
            id="mk-school"
            className="mk-input"
            required
            maxLength={160}
            value={form.school_name}
            onChange={set("school_name")}
            placeholder="Sunrise Public School"
          />
        </div>

        <div className="mk-field">
          <label htmlFor="mk-name">Your name</label>
          <input
            id="mk-name"
            className="mk-input"
            required
            maxLength={120}
            value={form.contact_name}
            onChange={set("contact_name")}
            placeholder="Meera Rao"
          />
        </div>

        <div className="mk-field">
          <label htmlFor="mk-phone">Phone</label>
          <input
            id="mk-phone"
            className="mk-input"
            required
            type="tel"
            inputMode="tel"
            maxLength={32}
            value={form.phone}
            onChange={set("phone")}
            placeholder="98765 43210"
          />
        </div>

        <div className="mk-field">
          <label htmlFor="mk-email">Email</label>
          <input
            id="mk-email"
            className="mk-input"
            required
            type="email"
            value={form.email}
            onChange={set("email")}
            placeholder="you@school.edu"
          />
        </div>

        <div className="mk-field">
          <label htmlFor="mk-count">
            Students on roll <i>— minimum 500</i>
          </label>
          <input
            id="mk-count"
            className="mk-input"
            type="number"
            inputMode="numeric"
            min={0}
            max={100000}
            value={form.student_count}
            onChange={set("student_count")}
            placeholder="840"
          />
        </div>

        <div className="mk-field" data-wide="true">
          <label htmlFor="mk-city">
            City <i>— optional</i>
          </label>
          <input
            id="mk-city"
            className="mk-input"
            maxLength={120}
            value={form.city}
            onChange={set("city")}
            placeholder="Guntur"
          />
        </div>

        <div className="mk-field" data-wide="true">
          <label htmlFor="mk-message">
            Anything we should know <i>— optional</i>
          </label>
          <textarea
            id="mk-message"
            className="mk-input"
            maxLength={2000}
            value={form.message}
            onChange={set("message")}
            placeholder="Two campuses, 300 hostellers, currently on Excel and WhatsApp."
          />
        </div>
      </div>

      <div className="mk-form-foot">
        <button className="mk-btn mk-btn-primary" type="submit" disabled={status === "sending"}>
          {status === "sending" ? "Sending…" : "Book a demo"}
        </button>
        <p className="mk-form-note">
          Goes straight to the founding team. No sales sequence, no newsletter.
        </p>
      </div>
    </form>
  );
}
