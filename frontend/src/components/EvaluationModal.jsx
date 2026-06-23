import { useState } from "react";
import Modal from "./Modal.jsx";
import { Flag } from "../flags.jsx";
import CalibrationChart from "./CalibrationChart.jsx";
import TitleRaceChart from "./TitleRaceChart.jsx";
import { useI18n } from "../i18n.jsx";

const pct = (v) => Math.round(v * 100) + "%";
const pct1 = (v) => (v * 100).toFixed(1) + "%";

// Colour a per-game RPS: lower is better (0 perfect). Thresholds are rough,
// only for the dot's hue — the number is what matters.
const rpsClass = (r) => (r <= 0.15 ? "good" : r <= 0.3 ? "ok" : "bad");

// How the forecast is doing vs the played results: proper scoring rules (RPS),
// a reliability diagram, and observed-vs-expected upsets.
export default function EvaluationModal({ data, date, model, history, onMatchClick, onClose }) {
  const { t, tn } = useI18n();
  const [info, setInfo] = useState(false);
  const [openRef, setOpenRef] = useState(null);
  const experts = model?.experts || [];
  const sources = model ? [
    { id: "elo", label: t("sm_rank_h"), desc: t("sm_fifa_desc"), ref: t("ref_elo") },
    { id: "books", label: t("sm_books"), desc: t("sm_books_desc"), ref: t("ref_books"), chips: model.books },
    { id: "goal", label: t("sm_goal_h"), ref: t("ref_goal") },
    { id: "host", label: t("sm_host_h"), ref: t("ref_host") },
  ] : [];

  if (!data || !data.n) {
    return (
      <Modal title={t("eval_title")} subtitle={t("eval_subtitle")} onClose={onClose}>
        <p className="muted">{t("eval_empty")}</p>
      </Modal>
    );
  }

  const ev = data;
  const upsetVars = {
    m: ev.n_upset, n: ev.n, exp: ev.upset_expected, p: pct(ev.upset_p),
  };

  return (
    <Modal title={t("eval_title")} subtitle={t("eval_subtitle")} onClose={onClose}>
      {/* Scorecard */}
      <div className="eval-cards">
        <div className="eval-card">
          <div className="eval-card-head">
            <span className="eval-card-label">{t("eval_rps")}</span>
            <button className="info-dot" aria-label={t("eval_rps")}
              aria-expanded={info} onClick={() => setInfo((v) => !v)}>i</button>
          </div>
          <div className="eval-card-val">{ev.mean_rps}</div>
          <div className="eval-card-sub">{t("eval_lower_better")}</div>
        </div>
        <div className="eval-card">
          <span className="eval-card-label">{t("eval_games")}</span>
          <div className="eval-card-val">{ev.n}</div>
          <div className="eval-card-sub">{t("eval_so_far")}</div>
        </div>
        <div className="eval-card">
          <span className="eval-card-label">{t("eval_called")}</span>
          <div className="eval-card-val">{ev.n_called}<span className="eval-card-of">/{ev.n}</span></div>
          <div className="eval-card-sub">{t("eval_called_exp", { exp: ev.called_expected })}</div>
        </div>
        <div className="eval-card">
          <span className="eval-card-label">{t("eval_upsets")}</span>
          <div className="eval-card-val">{ev.n_upset}</div>
          <div className="eval-card-sub">{t("eval_upsets_exp", { exp: ev.upset_expected })}</div>
        </div>
      </div>

      {info && (
        <div className="eval-info">
          <p>{t("eval_rps_info")}</p>
          <p className="muted small">{t("eval_bench")}</p>
          <p className="muted small">{t("eval_cite")}</p>
        </div>
      )}

      {/* Observed-vs-expected upset narrative (Q4) */}
      <p className="eval-narrative">{t("eval_upset_" + ev.upset_verdict, upsetVars)}</p>

      {/* Title-race evolution */}
      {history && history.dates && history.dates.length > 1 && (
        <>
          <h3>{t("eval_chart_h")}</h3>
          <p className="muted small">{t("eval_chart_help")}</p>
          <TitleRaceChart history={history} tn={tn} />
        </>
      )}

      {/* Calibration / reliability diagram */}
      <h3>{t("eval_calib_h")}</h3>
      <p className="muted small">{t("eval_calib_help")}</p>
      <CalibrationChart
        bins={ev.calibration}
        xLabel={t("eval_calib_x")}
        yLabel={t("eval_calib_y")}
        idealLabel={t("eval_calib_ideal")}
        modelLabel={t("eval_calib_model")}
      />
      {ev.n < 20 && <p className="muted small">{t("eval_smallN")}</p>}

      {/* Chronological game-by-game list */}
      <h3>{t("eval_games_h")}</h3>
      <div className="eval-list">
        {ev.games.map((g) => {
          const segs = [
            ["home", g.p_home, g.home],
            ["draw", g.p_draw, null],
            ["away", g.p_away, g.away],
          ];
          return (
            <button key={g.match_no} className="eval-row link"
              onClick={() => onMatchClick && onMatchClick(g.home, g.away)}>
              <span className="eval-row-date">{date && g.date}</span>
              <span className="eval-row-teams">
                <Flag team={g.home} />{tn(g.home)}
                <strong className="eval-row-score">{g.hs}–{g.as}</strong>
                {tn(g.away)}<Flag team={g.away} />
              </span>
              <span className="eval-bar" aria-hidden>
                {segs.map(([k, p]) => (
                  <span key={k} className={"seg " + k + (g.actual === k ? " actual" : "")}
                    style={{ width: pct(p) }} />
                ))}
              </span>
              <span className="eval-row-meta">
                <span className="eval-pactual">{t("eval_p_actual", { p: pct1(g.p_actual) })}</span>
                {g.upset
                  ? <span className="gm-tag upset">{t("gm_upset")}</span>
                  : g.as_predicted
                    ? <span className="gm-tag ok">✓</span>
                    : null}
                <span className={"eval-rps-dot " + rpsClass(g.rps)} title={"RPS " + g.rps} />
              </span>
            </button>
          );
        })}
      </div>

      {/* Sources & method (merged in; references behind (i)) */}
      {model && (
        <>
          <h3>{t("sm_title")}</h3>
          <p className="muted small">{t("sm_subtitle")}</p>
          <div className="src-list">
            {sources.map((s) => (
              <div className="src-item" key={s.id}>
                <div className="src-head">
                  <span className="src-label">{s.label}</span>
                  <button className="info-dot" aria-label={s.label}
                    aria-expanded={openRef === s.id}
                    onClick={() => setOpenRef((o) => (o === s.id ? null : s.id))}>i</button>
                </div>
                {s.chips && s.chips.length > 0 && (
                  <div className="odds-row">
                    {s.chips.map((b) => <span key={b} className="odds-chip">{b}</span>)}
                  </div>
                )}
                {s.desc && <p className="muted small src-desc">{s.desc}</p>}
                {openRef === s.id && <p className="src-ref small">{s.ref}</p>}
              </div>
            ))}
          </div>
          <h4 className="src-experts-h">{t("sm_experts_n", { n: experts.length })}</h4>
          <ul className="expert-list">
            {experts.map((e, i) => (
              <li key={i}>
                {e.winner && (
                  <span className="role role-winner" title={t("sm_tips")}>{e.winner}</span>
                )}
                {e.name}
                {e.outlet ? <span className="muted"> · {e.outlet}</span> : null}
              </li>
            ))}
          </ul>
          <p className="muted small">{t("sm_footer", { date: date || "" })}</p>
        </>
      )}
    </Modal>
  );
}
