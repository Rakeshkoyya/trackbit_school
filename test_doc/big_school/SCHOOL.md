# Sunrise International School — the school on paper

Derived from `generate.py`; regenerate rather than editing by hand.
This is the reference sheet — the click-by-click walkthrough is **SETUP.md**.

## Identity

| Field | Value |
|---|---|
| School | Sunrise International School |
| City | Hyderabad |
| Board | CBSE |
| Type | Day school + boarding (hostel) |
| Principal / admin | Vikram Rathore · principal@sunriseintl.edu.in |
| Classes | 1 to 8, one section each |
| Students | 240 (30 per class) — 66 hostellers, 174 day scholars |
| Teaching staff | 24 |
| Subjects | 10 |
| Class-subjects | 60 (= 60 syllabus files, 60 plans) |

## Academic year

| Field | Value |
|---|---|
| Label | 2026-27 |
| First day | 2026-06-01 |
| Last day | 2027-04-10 |
| Tracking starts | 2026-07-20 (Monday) — mid-year adoption |
| Working days | Mon-Sat (the app's default; no UI, no change needed) |
| Periods/day | 8 |
| Weekly capacity | 48 periods per class |
| Teaching days left after go-live | 169.2 (~28.2 weeks), net of holidays and exams |

> **Why mid-year.** The year opened on 1 June; the school buys the product in
> late July. `tracking_start_date` tells the planner to ignore everything before
> it — pre-adoption is *no data*, never a warning — so June and July do not show
> up as two months of missing attendance. Every syllabus in this pack is sized
> against the periods left **after** go-live, not the full year.

## The school day

Start **08:00** · **8** periods of **40 min** · lunch after period **5** for **40 min**. The wizard builds the timings from exactly those five numbers:

| Slot | From | To |
|---|---|---|
| Period 1 | 08:00 | 08:40 |
| Period 2 | 08:40 | 09:20 |
| Period 3 | 09:20 | 10:00 |
| Period 4 | 10:00 | 10:40 |
| Period 5 | 10:40 | 11:20 |
| Lunch | 11:20 | 12:00 |
| Period 6 | 12:00 | 12:40 |
| Period 7 | 12:40 | 13:20 |
| Period 8 | 13:20 | 14:00 |

## Subjects

Add them in the wizard **spelled exactly like this** — the staff sheet's
assignments resolve by name, and a mismatch lands in `unresolved`.

| # | Subject | Runs in |
|---|---|---|
| 1 | English | 1, 2, 3, 4, 5, 6, 7, 8 |
| 2 | Hindi | 1, 2, 3, 4, 5, 6, 7, 8 |
| 3 | Mathematics | 1, 2, 3, 4, 5, 6, 7, 8 |
| 4 | EVS | 1, 2, 3, 4 |
| 5 | Science | 5, 6, 7, 8 |
| 6 | Social Studies | 5, 6, 7, 8 |
| 7 | Sanskrit | 5, 6, 7, 8 |
| 8 | Computer Science | 1, 2, 3, 4, 5, 6, 7, 8 |
| 9 | Art & Craft | 1, 2, 3, 4 |
| 10 | Physical Education | 1, 2, 3, 4, 5, 6, 7, 8 |

## Weekly period split

Every row sums to **48**, so each class panel reads "48 of 48 periods/week allocated".

| Class | English | Hindi | Mathematics | EVS | Science | Social Studies | Sanskrit | Computer Science | Art & Craft | Physical Education | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | 11 | 9 | 10 | 6 | - | - | - | 4 | 4 | 4 | **48** |
| **2** | 11 | 8 | 10 | 7 | - | - | - | 4 | 4 | 4 | **48** |
| **3** | 10 | 8 | 10 | 8 | - | - | - | 4 | 4 | 4 | **48** |
| **4** | 10 | 8 | 10 | 8 | - | - | - | 4 | 4 | 4 | **48** |
| **5** | 8 | 6 | 9 | - | 7 | 6 | 4 | 4 | - | 4 | **48** |
| **6** | 8 | 6 | 8 | - | 8 | 6 | 4 | 4 | - | 4 | **48** |
| **7** | 8 | 5 | 8 | - | 8 | 7 | 4 | 4 | - | 4 | **48** |
| **8** | 7 | 5 | 9 | - | 9 | 7 | 4 | 4 | - | 3 | **48** |

## Teaching staff

24 teachers. The heaviest carries **22** of a possible 46 periods, so the
timetable generator can always place everyone without a clash.

Passwords are generated at import and shown **once** — copy them then.
Usernames are pinned in the sheet (`sis.` prefix) because `users.username`
is global across schools; without it the importer would quietly append a digit.

| Teacher | Username | Subject | Classes | Periods/week |
|---|---|---|---|---|
| Meena Iyer | `sis.meena.iyer` | English | 1, 2 | 22 |
| Radhika Nair | `sis.radhika.nair` | English | 3, 4 | 20 |
| Sunita Sharma | `sis.sunita.sharma` | Hindi | 1, 2 | 17 |
| Kavita Joshi | `sis.kavita.joshi` | Hindi | 3, 4 | 16 |
| Anita Reddy | `sis.anita.reddy` | Mathematics | 1, 2 | 20 |
| Deepa Menon | `sis.deepa.menon` | Mathematics | 3, 4 | 20 |
| Shalini Rao | `sis.shalini.rao` | EVS | 1, 2 | 13 |
| Priya Desai | `sis.priya.desai` | EVS | 3, 4 | 16 |
| Rajesh Verma | `sis.rajesh.verma` | English | 5, 6 | 16 |
| Nandini Bose | `sis.nandini.bose` | English | 7, 8 | 15 |
| Manoj Tiwari | `sis.manoj.tiwari` | Hindi | 5, 6 | 12 |
| Rekha Pillai | `sis.rekha.pillai` | Hindi | 7, 8 | 10 |
| Vikram Singh | `sis.vikram.singh` | Mathematics | 5, 6 | 17 |
| Lakshmi Kumar | `sis.lakshmi.kumar` | Mathematics | 7, 8 | 17 |
| Suresh Babu | `sis.suresh.babu` | Science | 5, 6 | 15 |
| Anjali Gupta | `sis.anjali.gupta` | Science | 7, 8 | 17 |
| Prakash Mehta | `sis.prakash.mehta` | Social Studies | 5, 6 | 12 |
| Geeta Chopra | `sis.geeta.chopra` | Social Studies | 7, 8 | 14 |
| Ramesh Shastri | `sis.ramesh.shastri` | Sanskrit | 5, 6, 7, 8 | 16 |
| Arun Banerjee | `sis.arun.banerjee` | Computer Science | 1, 2, 3, 4 | 16 |
| Farhan Khan | `sis.farhan.khan` | Computer Science | 5, 6, 7, 8 | 16 |
| Sneha Kulkarni | `sis.sneha.kulkarni` | Art & Craft | 1, 2, 3, 4 | 16 |
| Mohan Das | `sis.mohan.das` | Physical Education | 1, 2, 3, 4 | 16 |
| Imran Sheikh | `sis.imran.sheikh` | Physical Education | 5, 6, 7, 8 | 15 |

Total teaching load **384** = 8 classes x 48 periods.

## Syllabus

**60** files — one per class-subject — holding **818** chapters and
**2797** topics, every one of them sized (I3). Chapter titles follow the
NCERT books; topics are the three or four moves a teacher actually logs.

| Class | Files | Chapters | Topics | Periods of content | Periods available | Used |
|---|---|---|---|---|---|---|
| 1 | 7 | 90 | 320 | 974 | 1354 | 72% |
| 2 | 7 | 87 | 308 | 973 | 1354 | 72% |
| 3 | 7 | 90 | 317 | 973 | 1354 | 72% |
| 4 | 7 | 91 | 320 | 973 | 1354 | 72% |
| 5 | 8 | 104 | 368 | 974 | 1354 | 72% |
| 6 | 8 | 118 | 403 | 973 | 1354 | 72% |
| 7 | 8 | 119 | 387 | 973 | 1354 | 72% |
| 8 | 8 | 119 | 374 | 975 | 1354 | 72% |

## Calendar

Typed in on wizard step 7 (paint the range, pick the kind). There is no
calendar importer — `data/calendar_events.csv` is the list to copy from.

| Kind | Title | From | To | Costs |
|---|---|---|---|---|
| holiday | Muharram | 2026-06-26 | 2026-06-26 | whole day |
| holiday | Bonalu (local holiday) | 2026-07-13 | 2026-07-13 | whole day |
| holiday | Independence Day | 2026-08-15 | 2026-08-15 | whole day |
| exam_block | Unit Test 1 | 2026-08-24 | 2026-08-28 | periods 1, 2, 3 |
| celebration | Teachers' Day | 2026-09-05 | 2026-09-05 | whole day |
| holiday | Ganesh Chaturthi | 2026-09-14 | 2026-09-14 | whole day |
| holiday | Gandhi Jayanti | 2026-10-02 | 2026-10-02 | whole day |
| exam_block | Half-Yearly Examinations | 2026-10-06 | 2026-10-15 | whole day |
| holiday | Dussehra Break | 2026-10-19 | 2026-10-24 | whole day |
| holiday | Diwali Break | 2026-11-07 | 2026-11-14 | whole day |
| holiday | Guru Nanak Jayanti | 2026-11-24 | 2026-11-24 | whole day |
| event | Annual Sports Day | 2026-12-11 | 2026-12-11 | whole day |
| holiday | Christmas & New Year Break | 2026-12-24 | 2027-01-01 | whole day |
| exam_block | Unit Test 2 | 2027-01-04 | 2027-01-08 | periods 1, 2, 3 |
| holiday | Sankranti Break | 2027-01-14 | 2027-01-16 | whole day |
| holiday | Republic Day | 2027-01-26 | 2027-01-26 | whole day |
| celebration | Annual Day | 2027-02-05 | 2027-02-05 | whole day |
| holiday | Holi | 2027-03-03 | 2027-03-04 | whole day |
| exam_block | Annual Examinations | 2027-03-15 | 2027-03-27 | whole day |

## Fee structures

Office/admin only — teachers never see fees. Entered under **Fees > Structures**
(one per class + category + year); `data/fee_structures.csv` is the same list.

| Class | Category | Total (INR) | Installments |
|---|---|---|---|
| 1, 2 | Day Scholar | 42,000 | 3 |
| 1, 2 | Hosteller | 108,000 | 3 |
| 3, 4 | Day Scholar | 46,000 | 3 |
| 3, 4 | Hosteller | 112,000 | 3 |
| 5, 6 | Day Scholar | 52,000 | 3 |
| 5, 6 | Hosteller | 120,000 | 3 |
| 7, 8 | Day Scholar | 58,000 | 3 |
| 7, 8 | Hosteller | 128,000 | 3 |

## Hostel blocks

66 of 240 students are hostellers. These blocks live
under **Plan > Hostel**; the roster is computed from the linked classes, so a
new admission joins with zero edits.

| Block | Kind | Days | From | To | Classes | Warden |
|---|---|---|---|---|---|---|
| Morning Study | study | Mon-Sat | 06:00 | 07:00 | 5, 6, 7, 8 | Ramesh Shastri |
| Homework Hour | homework | Mon-Fri | 17:30 | 18:30 | 5, 6, 7, 8 | Farhan Khan |
| Evening Prep (juniors) | study | Mon-Sat | 19:00 | 20:00 | 1, 2, 3, 4 | Shalini Rao |
| Evening Prep (seniors) | study | Mon-Sat | 19:00 | 20:30 | 5, 6, 7, 8 | Vikram Singh |
| Saturday Yoga | activity | Sat | 06:30 | 07:30 | 1, 2, 3, 4, 5, 6, 7, 8 | Imran Sheikh |
| Sunday Games | activity | Sun | 16:30 | 18:00 | 1, 2, 3, 4, 5, 6, 7, 8 | Mohan Das |
