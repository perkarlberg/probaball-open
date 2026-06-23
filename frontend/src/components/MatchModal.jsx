import Modal from "./Modal.jsx";
import { Flag } from "../flags.jsx";
import { useI18n } from "../i18n.jsx";

const ipct = (v) => Math.round(v * 100) + "%";

// Single group match: win/draw/loss probabilities + most-likely score, with
// links to both teams and the group. Backs the crawlable /match/<a>-vs-<b>/
// pages (sleeper "[A] vs [B] prediction" searches).
export default function MatchModal({ match, group, onTeamClick, onGroupClick, onClose }) {
  const { t, tn } = useI18n();
  if (!match) return null;
  const top = Math.max(match.p_home, match.p_draw, match.p_away);
  const verdict =
    top === match.p_draw
      ? t("gm_draw")
      : t("gm_wins", { team: tn(top === match.p_home ? match.home : match.away) });

  return (
    <Modal
      title={
        <span className="mm-title">
          <Flag team={match.home} /> {tn(match.home)} <span className="mm-vs">–</span> {tn(match.away)} <Flag team={match.away} />
        </span>
      }
      subtitle={`${t("group_label", { g: group })} · ${t("gm_matchday", { n: match.matchday })}`}
      onClose={onClose}
    >
      <div className="mm-verdict">{verdict} · {ipct(top)}</div>

      <div className="gm-bar mm-bar">
        <span className="seg home" style={{ width: ipct(match.p_home) }} />
        <span className="seg draw" style={{ width: ipct(match.p_draw) }} />
        <span className="seg away" style={{ width: ipct(match.p_away) }} />
      </div>
      <div className="mm-probs">
        <button className="link" onClick={() => onTeamClick(match.home)}>
          {tn(match.home)} {ipct(match.p_home)}
        </button>
        <span>{t("gm_draw")} {ipct(match.p_draw)}</span>
        <button className="link" onClick={() => onTeamClick(match.away)}>
          {tn(match.away)} {ipct(match.p_away)}
        </button>
      </div>

      <p className="mm-score">{t("mm_score", { a: match.hg, b: match.ag })}</p>

      <div className="mm-links">
        <button className="link" onClick={() => onTeamClick(match.home)}>
          <Flag team={match.home} /> {tn(match.home)}
        </button>
        <button className="link" onClick={() => onGroupClick(group)}>
          {t("group_label", { g: group })}
        </button>
        <button className="link" onClick={() => onTeamClick(match.away)}>
          <Flag team={match.away} /> {tn(match.away)}
        </button>
      </div>
    </Modal>
  );
}
