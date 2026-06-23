// Map the engine's (Swedish) team names to flag-icons codes. England and
// Scotland use GB subdivision flags. flag-icons ships the SVGs in the bundle,
// so there are no runtime external requests.
export const TEAM_ISO = {
  Mexiko: "mx", Sydafrika: "za", Sydkorea: "kr", Tjeckien: "cz",
  Kanada: "ca", Schweiz: "ch", Qatar: "qa", Bosnien: "ba",
  Brasilien: "br", Marocko: "ma", Skottland: "gb-sct", Haiti: "ht",
  USA: "us", Paraguay: "py", Australien: "au", Turkiet: "tr",
  Tyskland: "de", Curacao: "cw", Elfenbenskusten: "ci", Ecuador: "ec",
  Nederländerna: "nl", Japan: "jp", Tunisien: "tn", Sverige: "se",
  Belgien: "be", Egypten: "eg", Iran: "ir", "Nya Zeeland": "nz",
  Spanien: "es", "Kap Verde": "cv", Saudiarabien: "sa", Uruguay: "uy",
  Frankrike: "fr", Senegal: "sn", Norge: "no", Irak: "iq",
  Argentina: "ar", Algeriet: "dz", Österrike: "at", Jordanien: "jo",
  Portugal: "pt", Colombia: "co", Uzbekistan: "uz", "DR Kongo": "cd",
  England: "gb-eng", Kroatien: "hr", Ghana: "gh", Panama: "pa",
};

// Region subtag (from navigator.languages, e.g. "es-MX" -> "MX") -> team name.
// Built by inverting TEAM_ISO; subdivision codes map their GB region too.
const REGION_TEAM = {};
for (const [team, iso] of Object.entries(TEAM_ISO)) {
  REGION_TEAM[iso.toUpperCase()] = team;
}

export function teamForRegion(region) {
  if (!region) return null;
  const r = region.toUpperCase();
  return REGION_TEAM[r] || REGION_TEAM[`GB-${r}`] || null;
}

export function Flag({ team, className = "" }) {
  const iso = TEAM_ISO[team];
  if (!iso) return null;
  return (
    <span
      className={`fi fi-${iso} team-flag ${className}`}
      role="img"
      aria-label={team}
    />
  );
}
