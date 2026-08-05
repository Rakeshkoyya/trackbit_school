/** Students — two halves, and they are two different KINDS of fact (founder, 2026-08-05).
 *
 *   Directory  the ADMINISTRATION record. Name, parents, phone, date of birth,
 *              class, category. Entered once at admission, corrected
 *              occasionally, admin-only to write, and the thing the office
 *              opens when somebody rings.
 *   Academics  the record the school MAKES. Register, class log, homework,
 *              exams, report. Written every day by teachers and read as a
 *              trend, never as a field.
 *
 * They were one screen and one table, and it could serve neither: the columns a
 * clerk needs ("mother's mobile") and the columns a principal needs ("average,
 * last homework") do not belong in one row, and the people who read them arrive
 * on different days with different questions.
 *
 * This layout is deliberately a pass-through. Each half owns its own header —
 * Directory has no tabs at all, and the Academics tab bar would be noise above
 * a roster the admin came to correct a phone number in. `/students/[id]`, the
 * child's report, sits outside both because it is a document, not a tab.
 *
 * Bands left with V1-9/BD-2 and its tab is gone: the support programme has its
 * own area, and `/students/bands` now redirects there (`next.config.ts`).
 */
export default function StudentsLayout({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>;
}
