import Modal from "./Modal.jsx";
import { Flag } from "../flags.jsx";
import KOBar from "./KOBar.jsx";
import { useI18n } from "../i18n.jsx";

const ipct = (v) => Math.round(v * 100) + "%";
const KO_LBL = { R32: "tm_rnd_r32", R16: "tm_rnd_r16", Kvartsfinal: "tm_rnd_quarter",
                 Semifinal: "tm_rnd_semi", Final: "tm_rnd_final" };

// Single match page (/match/<a>-vs-<b>/): group ties show win/draw/loss + score;
// knockout ties show each team's chance to ADVANCE, split 90' vs ET/penalties.
export default function MatchModal({ match, group, ko, onTeamClick, onGroupClick, onClose }) {
  const { t, tn } = useI18n();

  if (ko) {
    const hAdv = ko.hReg + ko.hEt, aAdv = ko.aEt + ko.aReg;
    const winner = hAdv >= aAdv ? ko.home : ko.away;
    return (
      <Modal
        title={
          <span className="mm-title">
            <Flag team={ko.home} /> {tn(ko.home)} <span className="mm-vs">–</span> {tn(ko.away)} <Flag team={ko.away} />
          </span>
        }
        subtitle={t(KO_LBL[ko.round] || "tm_rnd_r16")}
        onClose={onClose}
      >
        <div className="mm-verdict">{t("gm_wins", { team: tn(winner) })} · {t("tm_ko_adv", { pct: ipct(Math.max(hAdv, aAdv)) })}</div>
        <KOBar home={ko.home} away={ko.away} hReg={ko.hReg} hEt={ko.hEt} aEt={ko.aEt} aReg={ko.aReg} />
        <div className="mm-probs">
          <button className="link" onClick={() => onTeamClick(ko.home)}>{tn(ko.home)} {ipct(hAdv)}</button>
          <button className="link" onClick={() => onTeamClick(ko.away)}>{tn(ko.away)} {ipct(aAdv)}</button>
        </div>
        <p className="mm-score muted small">
          {tn(ko.home)}: {t("tm_ko_split", { reg: ipct(ko.hReg), et: ipct(ko.hEt) })} · {tn(ko.away)}: {t("tm_ko_split", { reg: ipct(ko.aReg), et: ipct(ko.aEt) })}
        </p>
        <div className="mm-links">
          <button className="link" onClick={() => onTeamClick(ko.home)}><Flag team={ko.home} /> {tn(ko.home)}</button>
          <button className="link" onClick={() => onTeamClick(ko.away)}><Flag team={ko.away} /> {tn(ko.away)}</button>
        </div>
      </Modal>
    );
  }

  if (!match) return null;
  const top = Math.max(match.p_home, match.p_draw, match.p_away);
  const verdict =
    top === match.p_draw
      ? t("gm_draw")
      : t("gm_wins", { team: tn(top === match.p_home ? match.home : match.away) });
  // Played group games lead with the actual full-time score (+ predicted/upset
  // tags); the model's pre-match odds stay below as context.
  const r = match.result;
  const resultVerdict = r
    ? r.home > r.away
      ? t("gm_wins", { team: tn(match.home) })
      : r.away > r.home
        ? t("gm_wins", { team: tn(match.away) })
        : t("gm_draw")
    : null;

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
      {r ? (
        <div className="mm-verdict mm-result">
          <strong className="mm-final">{r.home}–{r.away}</strong>
          <span>{resultVerdict}</span>
          {match.as_predicted && <span className="gm-tag ok">✓ {t("gm_as_pred")}</span>}
          {match.upset && <span className="gm-tag upset">{t("gm_upset")}</span>}
        </div>
      ) : (
        <div className="mm-verdict">{verdict} · {ipct(top)}</div>
      )}

      {r && <p className="mm-cap muted small">{t("mm_prematch")}</p>}
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

      {!r && <p className="mm-score">{t("mm_score", { a: match.hg, b: match.ag })}</p>}

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
