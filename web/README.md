# TrackBit Web

The frontend for **TrackBit** — simple, stress-free task management for small teams.
Next.js + React + Tailwind.

> New to the project? This guide takes you from a fresh clone to the app running
> in your browser. If anything is unclear, ask your team lead.

---

## What's in here

- **Next.js 16** + **React 19** (App Router)
- **Tailwind CSS v4** (CSS-first theming in `src/app/globals.css`)
- **TanStack Query** for data fetching/caching
- Talks to the **TrackBit API** backend (a separate repo, `trackbit_api`)

---

## Prerequisites

1. **Node.js 20+** (Next.js 16 requires it). Get it from https://nodejs.org/ or via
   `nvm`. Check with `node -v`.
2. **The backend running** — the web app is just a UI; it needs the `trackbit_api`
   server running (default `http://localhost:8000`). Set that up first using its
   own README.

---

## Setup (first time)

```bash
# 1. Clone and enter the repo
git clone <repo-url> trackbit_web
cd trackbit_web

# 2. Install dependencies
npm install

# 3. Create your local environment file from the template
cp .env.example .env.local                 # macOS / Linux
# Copy-Item .env.example .env.local         # Windows PowerShell

# 4. Make sure NEXT_PUBLIC_API_BASE_URL in .env.local points at the running
#    backend. The default (http://localhost:8000/api/v1) is correct if you run
#    the API locally on port 8000.
```

---

## Running the app

```bash
# Make sure the backend (trackbit_api) is running first, then:
npm run dev
```

Open **http://localhost:3000** in your browser.

> Sign in with the demo account created by the backend's seed script:
> **kc@demo.trackbit.app** / **demo1234**

If the page loads but login/data fails, your backend isn't running or
`NEXT_PUBLIC_API_BASE_URL` is wrong.

---

## Everyday commands

```bash
npm run dev          # start the dev server (hot-reloads on change)
npm run build        # production build (also type-checks)
npm run lint         # eslint
npx tsc --noEmit     # type-check only
```

---

## Project layout

```
src/
  app/               # routes (App Router): (app)/home, boards, task, ...
  components/        # UI — boards/, tasks/, ui/ (shared primitives)
  lib/               # api client, types, helpers
  contexts/          # auth context
```

> Note: this repo runs a newer Next.js with some breaking changes from older
> versions — see `AGENTS.md`. When in doubt, check `node_modules/next/dist/docs/`.

---

## Environment variables

Only one is needed for local dev (see `.env.example`):

| Variable                   | What it is                                  |
| -------------------------- | ------------------------------------------- |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL of the backend API, ending `/api/v1` |

`.env.local` is gitignored — never commit it. Anything prefixed `NEXT_PUBLIC_`
is exposed to the browser, so never put secrets there.
