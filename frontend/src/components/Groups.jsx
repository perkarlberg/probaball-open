import { useI18n } from "../i18n.jsx";

const pct = (v) => Math.round(v * 100) + "%";

// The bar shows advancement chance: a solid segment for top-2 (direct
// qualification) plus a fainter extension for 3rd place — the eight best
// third-placed teams (of twelve groups) also reach the Round of 32.
export default function Groups({ groups, onGroupClick }) {
  const { t, tn } = useI18n();
  const names = Object.keys(groups).sort();
  return (
    <div className="groups-grid">
      {names.map((g) => (
        <div
          key={g}
          className="group-card clickable"
          onClick={() => onGroupClick(g)}
        >
          <h3>{t("group_label", { g })} <span className="group-more">{t("details")}</span></h3>
          <table className="group-table">
            <thead>
              <tr>
                <th>{t("col_team")}</th>
                <th className="num">{t("g_first")}</th>
                <th className="num">{t("g_second")}</th>
                <th className="num">{t("g_top2")}</th>
              </tr>
            </thead>
            <tbody>
              {groups[g].map((row) => {
                const top2 = row.p_first + row.p_second;
                const top3 = top2 + row.p_third;
                return (
                  <tr key={row.team}>
                    <td className="team">
                      <span
                        className="qual-bar third"
                        style={{ width: `${top3 * 100}%` }}
                        aria-hidden
                      />
                      <span
                        className="qual-bar"
                        style={{ width: `${top2 * 100}%` }}
                        aria-hidden
                      />
                      <span className="qual-name">{tn(row.team)}</span>
                    </td>
                    <td className="num">{pct(row.p_first)}</td>
                    <td className="num">{pct(row.p_second)}</td>
                    <td className="num strong">{pct(top2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
