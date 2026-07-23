# TrackBit School — Generative UI ("GA") Specification

**Version:** 1.0 · 2026-07-24 · founder-approved direction (chat discussion 2026-07-24)
**Cite as:** `GA §x.y`. Conflict order stays **SPRD2 > this doc > architecture doc > SPRD v1**,
except where a section here explicitly extends the Lucy layer (LU) — then this doc governs.

---

## §1 Vision

Every product lives somewhere between **direct manipulation** (hand-built screens, fixed IA)
and **agentic prompting** (a chat box that answers anything and persists nothing). TrackBit's
AI layer takes the middle road — **generative UI**: the agent composes real product surfaces
out of a fixed, hand-built component kit, and the compositions become part of the product.

Three capabilities, in order:

1. **Composed answers** — a complex ask ("give me a report on Rohit, class 8, I'm meeting his
   parents") returns not one widget but a *sectioned mini-dashboard*: narrative + widgets,
   saved as a **View** the user can reopen, refresh and print.
2. **Interactive questions** — the agent asks instead of guessing ("there are 3 Rohits — which
   class?") via option chips in chat, and uses the same primitive to *suggest* turning a
   repeated ask into a module.
3. **Custom modules** — a school asks for a surface that doesn't exist ("a proper attendance
   dashboard") and the agent generates a **module spec** — controls + layout + component
   bindings — previews it live in chat, and on human confirm it lands in that school's
   sidebar. Only that school sees it. The product evolves per school, through use.

The founder-level flywheel: since the operator (super-admin) runs every school, generated
modules are **demand telemetry**. When several schools generate the same module, it gets
promoted into a first-class product feature.

## §2 Doctrine (inherited, non-negotiable)

The two rules that made Lucy safe extend to everything here:

- **The model never types data.** It picks representations; numbers are materialized
  server-side from stored tool results (`widgets.py`). A key the model invents raises
  `WidgetConfigError` back to the model. Views and modules store **bindings + snapshots**,
  never model-authored numbers.
- **Every AI output lands in a human-confirm surface.** A module is a pending action writ
  large: draft → live preview → explicit save. Nothing enters the sidebar without a tap.

And the fences ride along mechanically, because everything executes through the existing
registry with the *viewing member's* authority: org scoping (law 1), RLS (law 2), teacher
scoping, the fee fence (admin-only), P4 (bands never parent-facing). **All GA surfaces are
staff-only.** A parent-facing generated surface is OUT — it would need its own curated
projection story and is a future founder decision.

**Specs, not code.** The agent never emits JSX/HTML/SQL. It emits declarative specs
interpreted by fixed renderers. This is what keeps generated surfaces migration-safe
(validate specs centrally on schema change), XSS-free, on-design, and supportable.

## §3 The School UI Kit (GA-0)

One catalog of renderable components, shared by chat widgets, Views, and (later) modules.

### §3.1 Component manifest

Every widget type is registered in a `CATALOG` (backend `widgets.py`) with a manifest:

| field          | meaning                                                                 |
|----------------|-------------------------------------------------------------------------|
| `name`         | the widget type id (`table`, `meter`, `radar`, …)                        |
| `summary`      | one line: what it renders                                                |
| `when_to_use`  | agent guidance — the sentence that steers selection                      |
| `config_guide` | the config contract line injected into `render_widget`'s description     |
| `role`         | `academic` \| `admin` — admin-only components never appear in a teacher's render enum |
| `shaper`       | the server-side function that extracts data by keys/paths (fabrication-proof) |

`CONFIG_GUIDE`, `WIDGET_TYPES` and the `render_widget` tool schema are **generated from the
catalog** — one source of truth. Role filtering happens at schema time (a teacher's model
never sees admin-only components), mirroring the tool registry.

**Binding slots:** each `ToolSpec.widgets` tuple names the components its result renders
well as — the tool→component compatibility map the agent (and later the module validator)
reads.

### §3.2 Catalog v2 (GA-0 target: 17 types)

Existing 13: `table` `stat_group` `bar_chart` `line_chart` `donut` `rag_board` `roster_grid`
`timeline` `report_card` `student_card` `alert_list` `progress` `markdown`.

New in GA-0, each backed by an existing chart-kit mark and an existing feeder tool:

- **`meter`** — one gauge (0–100%): fee collection, attendance pulse, syllabus pace.
- **`radar`** — profile shape over axes, ≤2 series: skill profile vs class average.
- **`area_chart`** — one filled measure over time: the 14-day attendance pulse.
- **`drilldown`** — generic two-level expandable list with per-group stats: chapters→topics
  from student growth, unit→topic progress.

### §3.3 Promote, don't fork

Lucy's chart widgets currently duplicate the product chart kit. GA-0 rewires
`components/lucy/widgets/charts.tsx` to consume `components/charts/school-charts.tsx`
(ColumnChart, TrendLine, Donut, Gauge, AbilityRadar, PulseArea) — one implementation, one
dynamic Recharts chunk, so dashboard, report card, class analytics and every Lucy/View/module
surface render identically. Further screen-component promotion (grouped student table,
identity band) continues opportunistically as GA-3/GA-4 need them.

### §3.4 Component gallery

An internal page (super-admin only, `/platform` area) rendering **every catalog component
from committed sample data**. It is the QA surface, the design ground truth, and the check
that manifests stay honest. Done-when for any new component: it renders in the gallery.

## §4 Interactive questions (GA-1)

A new internal tool `ask_user(question, options[], allow_free_text?)`. Calling it **ends the
turn**: the stream emits a `question` event, the client renders option chips (+ free text),
and the tapped answer is sent as the next user message (label + any carried id), starting a
fresh turn. No pause/resume machinery — a question is a turn that ends in a card, exactly
like the confirm card. The question persists on the assistant message (`meta.question`) so
history rehydrates.

Prompt rules: never guess between real candidates (ids especially); never ask when one match
exists; at most one question per turn; options carry the resolved ids so the next turn does
not re-search.

## §5 Views — composed answers (GA-1)

A **View** is a saved composition: title + optional summary line + ordered sections, each
`{heading, narrative?, widgets[]}`. New internal tool
`compose_view(title, summary?, sections[])` where each section references **widget ids
already rendered this turn** — the model can only compose what was materialized, so a View
is fabrication-proof by construction.

Storage: `lucy_views` — org-scoped + RLS, **member-private** like conversations,
self-contained (owns copies of its widget envelopes: snapshot + `source_tool`/`source_params`
bindings), so a View survives its conversation's deletion. Refresh re-executes each widget's
source with the viewer's live role (pin-board semantics: never 500, fall back to snapshot).
Endpoints: list / detail / refresh / delete under `/lucy/views`. The Lucy landing page lists
recent Views beside pins; a View has its own page, refreshable and printable.

**Request signatures (recorded from GA-1, used from GA-3):** every saved View records a
signature — the sorted set of source tools behind it plus a scope hint. This is the
frequency signal later phases read. Recording starts now so GA-3 has months of data.

## §6 IA awareness + navigation (GA-2)

- A compact **app map** (routes, what each page shows, params) joins the system prompt.
- A `navigate` internal tool returns a deep link rendered as a button in chat.
- Widget envelopes gain optional `href` (student_card → `/students/[id]`).

GA-2 is the prerequisite for honest module judgment: *never generate what already exists —
link to it.*

## §7 Custom modules (GA-3)

`custom_modules`: org-scoped + RLS, append-only versions (law 3), `status` draft→published,
role visibility (`admin` | `all_staff`), `spec` JSONB:

```
{ name, icon, nav: {placement}, visibility,
  controls: [{id, kind: class_picker|date_range|subject_picker|toggle, default}],
  sections: [{heading?, widgets: [{type, title, config,
              binding: {tool|dataset, params}}]}] }   // params may reference controls
```

The renderer is one fixed page (`/m/[slug]`) that resolves controls → executes bindings with
the **viewing member's** authority → materializes through the same shapers. The sidebar
gains a dynamic tail fed from the org's published modules. Admin manage screen
(rename/archive/visibility); super-admin sees all modules across orgs.

Flow: ask → agent checks app map + existing modules → drafts spec → **live preview in chat**
(same renderer) → conversational iteration → confirm-gated save → sidebar.

**Suggestion judgment** (model proposes only what the deterministic layer allows):
- explicit ask → always;
- duplicate of a core page or existing module → never (navigate instead, needs GA-2);
- frequency-hinted → the signature counter injects "asked N× in M days" into context; the
  model may suggest only when the hint is present;
- anti-nag: declined signature → cooldown, max one suggestion per conversation, suggestion
  only *after* the delivered answer.

## §8 Dataset layer (GA-4)

Custom modules need data shaped for tables-with-filters, not conversational answers. A
**dataset** is a hand-written, parameterized, role-fenced queryable view (declared filters +
columns) registered beside tools: `attendance_history` first (class / date-range / student),
then homework completion, lesson-log history, session records. Datasets are the *only*
schema-shaped surface the agent gets — **AI-generated SQL stays OUT** (it would bypass the
service-level fences P4 lives in, and make every migration a breaking change for saved
modules). A school asking for data no dataset covers is a roadmap signal, not a codegen
trigger.

## §9 Packets

- **GA-0 — School UI Kit.** Catalog manifests; 4 new types (meter, radar, area_chart,
  drilldown) + shapers + renderers; Lucy charts rewired onto the product chart kit; feeder
  tools' `widgets` tuples updated; component gallery. *Done-when:* every type renders in the
  gallery from sample data; shaper tests green; web gates green; existing Lucy widgets
  unchanged in behavior.
- **GA-1 — Views + questions.** `compose_view`, `lucy_views` (+ migration + RLS), view
  endpoints/pages, `ask_user` + question event + chips, signature recording, prompt updates.
  *Done-when:* a meeting-prep ask disambiguates via chips then yields a saved, refreshable,
  printable View; P4/fee fences asserted in tests.
- **GA-2 — IA + navigation.** App map, `navigate` tool, widget `href`.
- **GA-3 — Custom modules v1.** Table + spec + renderer page + dynamic sidebar + preview +
  confirm-gated save + suggestion judgment + manage screens.
- **GA-4 — Datasets.** `attendance_history` et al.; module controls bind to dataset filters.
- **GA-5 — Flywheel.** Usage telemetry, cross-org module gallery, promote-to-product.

## §10 Out of scope (binding)

Per-school generated **code** of any kind · AI-generated SQL · parent-facing generated
surfaces · module writes (modules are read-only compositions; capture stays in the
hand-built flows) · cross-school sharing of modules before GA-5 · any surface that shows
bands to non-staff (P4) or fees to teachers.
