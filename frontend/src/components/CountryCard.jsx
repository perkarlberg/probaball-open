import { Flag } from "../flags.jsx";
import { useI18n } from "../i18n.jsx";

const pct = (v) => (v * 100).toFixed(1) + "%";

// Highlight card for the visitor's own nation (locale-detected or chosen),
// shown only when that country is one of the 48 participants.
export default function CountryCard({ team, rank, onOpen, onChange }) {
  const { t, tn } = useI18n();
  if (!team) return null;
  return (
    <div className="country-card-wrap">
      <button className="country-card" onClick={() => onOpen(team.team)}>
        <Flag team={team.team} className="country-card-flag" />
        <span className="country-card-body">
          <span className="country-card-eyebrow">{t("cc_eyebrow")}</span>
          <span className="country-card-name">{tn(team.team)}</span>
          <span className="country-card-stat">
            {t("cc_stat", { pct: pct(team.champion) })}{rank ? ` · #${rank}` : ""}
          </span>
        </span>
      </button>
      <button className="link country-card-change" onClick={onChange}>
        {t("cc_change")}
      </button>
    </div>
  );
}
