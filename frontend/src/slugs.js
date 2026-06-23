import { TEAM_NAMES } from "./i18n.jsx";

// URL slugs derived from the English team name (stable, ASCII, language-neutral)
// so routes look like /lag/south-korea regardless of the visitor's language.
// The Python prerender uses the identical rule on the team's name_en.
const DIACRITICS = /[̀-ͯ]/g;
export const slugify = (s) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(DIACRITICS, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

const EN = TEAM_NAMES.en;
const SLUG_TEAM = {};
const TEAM_SLUG = {};
for (const sv in EN) {
  const s = slugify(EN[sv]);
  SLUG_TEAM[s] = sv;
  TEAM_SLUG[sv] = s;
}

export const teamForSlug = (s) => (s ? SLUG_TEAM[s.toLowerCase()] || null : null);
export const slugForTeam = (sv) => TEAM_SLUG[sv] || slugify(sv);
