import Modal from "./Modal.jsx";
import { Flag } from "../flags.jsx";
import { useI18n } from "../i18n.jsx";

const pct = (v) => (v * 100).toFixed(1) + "%";
const ipct = (v) => Math.round(v * 100) + "%";

// Finishing-position distribution for one group. Columns 1st–4th; the top-2
// (direct qualification) zone is tinted, with a lighter tint on 3rd place —
// the eight best of twelve third-placed teams also advance to the Round of 32.
export default function GroupModal({ group, rows, matches, onTeamClick, onMatchClick, onClose }) {
  const { t, tn, lang } = useI18n();
  const mds = matches && matches.length ? [...new Set(matches.map((m) => m.matchday))] : [];
  const fmtDate = (d) => {
    try {
      return new Date(d + "T12:00:00Z").toLocaleDateString(lang === "sv" ? "sv-SE" : lang, {
        month: "short", day: "numeric",
      });
    } catch { return d; }
  };
  return (
    <Modal
      title={t("group_label", { g: group })}
      subtitle={t("gm_subtitle")}
      onClose={onClose}
    >
      {mds.length > 0 && (
        <>
          <h3>{t("gm_results")}</h3>
          {mds.map((md) => (
            <div key={md} className="gm-md">
              <div className="gm-md-label">{t("gm_matchday", { n: md })}</div>
              {matches.filter((m) => m.matchday === md).map((m, i) => {
                const top = Math.max(m.p_home, m.p_draw, m.p_away);
                const verdict =
                  top === m.p_draw
                    ? t("gm_draw")
                    : t("gm_wins", { team: tn(top === m.p_home ? m.home : m.away) });
                return (
                  <div key={i} className={"gm-match" + (m.result ? " played" : "")}>
                    {m.date && <span className="gm-date">{fmtDate(m.date)}</span>}
                    <button className="gm-team home link" onClick={() => onTeamClick(m.home)}>
                      {tn(m.home)}<Flag team={m.home} />
                    </button>
                    {m.result ? (
                      <div className="gm-score">
                        <strong>{m.result.home}–{m.result.away}</strong>
                        {m.as_predicted && <span className="gm-tag ok">✓ {t("gm_as_pred")}</span>}
                        {m.upset && <span className="gm-tag upset">{t("gm_upset")}</span>}
                      </div>
                    ) : (
                      <div className="gm-odds">
                        <div className="gm-bar">
                          <span className="seg home" style={{ width: ipct(m.p_home) }} />
                          <span className="seg draw" style={{ width: ipct(m.p_draw) }} />
                          <span className="seg away" style={{ width: ipct(m.p_away) }} />
                        </div>
                        <div className="gm-probs">
                          <span>{ipct(m.p_home)}</span>
                          <span>{t("gm_draw")} {ipct(m.p_draw)}</span>
                          <span>{ipct(m.p_away)}</span>
                        </div>
                      </div>
                    )}
                    <button className="gm-team away link" onClick={() => onTeamClick(m.away)}>
                      <Flag team={m.away} />{tn(m.away)}
                    </button>
                    {m.result ? (
                      <button className="gm-verdict link"
                        onClick={() => onMatchClick && onMatchClick(m.home, m.away)}>
                        {t("gm_detail")} →
                      </button>
                    ) : (
                      <button className="gm-verdict link"
                        onClick={() => onMatchClick && onMatchClick(m.home, m.away)}>
                        {verdict} · {ipct(top)} →
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </>
      )}

      <table className="modal-table">
        <thead>
          <tr>
            <th>{t("col_team")}</th>
            <th className="num qual">{t("g_first")}</th>
            <th className="num qual">{t("g_second")}</th>
            <th className="num qual3">{t("g_third")}</th>
            <th className="num">{t("g_fourth")}</th>
            <th className="num">{t("g_avg")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.team}>
              <td>
                <button className="link" onClick={() => onTeamClick(row.team)}>
                  <Flag team={row.team} />
                  {tn(row.team)}
                </button>
              </td>
              <td className="num qual strong">{pct(row.p_first)}</td>
              <td className="num qual">{pct(row.p_second)}</td>
              <td className="num qual3">{pct(row.p_third)}</td>
              <td className="num">{pct(row.p_fourth)}</td>
              <td className="num muted">{row.expected_pos.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">{t("gm_note")}</p>
    </Modal>
  );
}
