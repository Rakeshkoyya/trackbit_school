/** The canonical Indian state / UT list, mirroring `api/app/core/indian_states.py`.
 *
 *  This exists so the browser can offer a PICKER rather than a text box. The
 *  server normalises whatever it receives, so a typed value is not dangerous —
 *  but an unresolvable one silently scopes a school to no regional dates at
 *  all, and the failure has no symptom: the suggestions feed is simply thin,
 *  forever, with nothing on screen to say why.
 *
 *  Keep this list identical to the Python one. It is duplicated rather than
 *  fetched because it is a fixed constitutional fact, not configuration, and a
 *  round trip to render a dropdown would be silly.
 */

export const INDIAN_STATES = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
] as const;

export const INDIAN_UNION_TERRITORIES = [
  "Andaman and Nicobar Islands",
  "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Jammu and Kashmir",
  "Ladakh",
  "Lakshadweep",
  "Puducherry",
] as const;

export const ALL_INDIAN_STATES: readonly string[] = [
  ...INDIAN_STATES,
  ...INDIAN_UNION_TERRITORIES,
];

/** True when a stored value is one the catalogue can actually match.
 *  Used to warn on a school whose state was typed before the picker existed —
 *  the value is kept (never silently rewritten), but the admin is told it
 *  matches nothing. */
export function isCanonicalState(value: string | null | undefined): boolean {
  return !!value && ALL_INDIAN_STATES.includes(value);
}
