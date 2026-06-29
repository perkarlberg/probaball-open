import Modal from "./Modal.jsx";
import Histogram from "./Histogram.jsx";
import PlacementHistogram from "./PlacementHistogram.jsx";
import TitleRaceChart from "./TitleRaceChart.jsx";
import { Flag } from "../flags.jsx";
import { useI18n } from "../i18n.jsx";

const pct = (v) => (v == null ? "–" : (v * 100).toFixed(1) + "%");
const american = (o) => (o == null ? "–" : o > 0 ? `+${o}` : `${o}`);
const ROLE_KEY = { winner: "role_winner", finalist: "role_finalist", semifinalist: "role_semifinalist" };

// Per-team deep dive: FIFA rank, bookmaker odds, expert predictions, and
// histograms of simulated tournament + group-stage placement.
export default function TeamModal({ team, groupRow, matches, history, onMatchClick, onClose, isMyTeam, onSetMyTeam, numExperts = 18 }) {
  const { t, tn } = useI18n();
  // Final-placement distribution (best -> worst) from cumulative reach probs.
  // Each band = share of all simulations where this was the team's final result.
  const bands = [
    team.champion,
    Math.max(0, team.final - team.champion),
    Math.max(0, team.semi - team.final),
    Math.max(0, team.quarter - team.semi),
    Math.max(0, team.r16 - team.quarter),
    Math.max(0, (team.r32 ?? 0) - team.r16),
    Math.max(0, 1 - (team.r32 ?? 0)),
  ];
  const roundLabels = [
    "🏆",
    t("tm_rnd_final"),
    t("tm_rnd_semi"),
    t("tm_rnd_quarter"),
    t("tm_rnd_r16"),
    t("tm_rnd_r32"),
    t("tm_rnd_group"),
  ];
  const stages = bands.map((v, i) => ({ label: roundLabels[i], value: v, highlight: i === 0 }));

  // Spread each round's probability evenly across its placement range, giving a
  // share for each of the 48 final positions (1 = champion … 33-48 = group out).
  const spans = [1, 1, 2, 4, 8, 16, 16]; // teams per band: 1,2,3-4,5-8,9-16,17-32,33-48
  const positions = [];
  bands.forEach((v, i) => {
    for (let j = 0; j < spans[i]; j++) positions.push(v / spans[i]);
  });
  const groupBars = groupRow
    ? [
        { label: t("g_first"), value: groupRow.p_first, highlight: true },
        { label: t("g_second"), value: groupRow.p_second, highlight: true },
        { label: t("g_third"), value: groupRow.p_third },
        { label: t("g_fourth"), value: groupRow.p_fourth },
      ]
    : null;
  const books = Object.entries(team.book_odds || {});

  return (
    <Modal
      title={<><Flag team={team.team} className="title-flag" />{tn(team.team)}</>}
      subtitle={t("tm_subtitle", { group: t("group_label", { g: team.group }), r: team.rating })}
      onClose={onClose}
    >
      {team.champion_prev != null && team.champion != null &&
        (team.champion_prev * 100).toFixed(1) !== (team.champion * 100).toFixed(1) && (
        <p className={"tm-trend " + (team.champion > team.champion_prev ? "up" : "down")}>
          {t(team.champion > team.champion_prev ? "tm_champ_up" : "tm_champ_down", {
            from: (team.champion_prev * 100).toFixed(1),
            to: (team.champion * 100).toFixed(1),
          })}
        </p>
      )}

      {matches && matches.length > 0 && (
        <>
          <h3>{t("tm_matches")}</h3>
          <ul className="tm-matches">
            {matches.map((m) => {
              const home = m.home === team.team;
              const opp = home ? m.away : m.home;
              const played = !!m.result;
              let cls = "", note = null, scoreTxt = "";
              if (played) {
                const gf = home ? m.result.home : m.result.away;
                const ga = home ? m.result.away : m.result.home;
                cls = gf > ga ? "win" : gf === ga ? "draw" : "loss";
                scoreTxt = `${gf}–${ga}`;
                note = m.upset
                  ? <span className="gm-tag upset">{t("gm_upset")}</span>
                  : m.as_predicted ? <span className="gm-tag ok">✓</span> : null;
              }
              const win = home ? m.p_home : m.p_away;
              return (
                <li key={m.home + m.away}>
                  <button className="tm-match link" onClick={() => onMatchClick && onMatchClick(m.home, m.away)}>
                    <span className="tm-match-date">{m.date}</span>
                    <span className="tm-match-opp"><Flag team={opp} />{tn(opp)}</span>
                    {played
                      ? <span className={"tm-match-score " + cls}>{scoreTxt}</span>
                      : <span className="tm-match-pred">{t("tm_pred", { pct: (win * 100).toFixed(0) + "%" })}</span>}
                    {note}
                  </button>
                </li>
              );
            })}
            {(team.next_ko || []).map((k) => {
              const lbl = { R32: "tm_rnd_r32", R16: "tm_rnd_r16", Kvartsfinal: "tm_rnd_quarter",
                            Semifinal: "tm_rnd_semi", Final: "tm_rnd_final" }[k.round] || "tm_rnd_r16";
              const p0 = (v) => (v * 100).toFixed(0) + "%";
              if (k.known) {
                // Both teams' chance to ADVANCE, split into a 90' win vs winning
                // a level tie in extra time / penalties (no draw outcome in a KO).
                const side = (lblText, flagTeam, adv, reg, et) => (
                  <span className="tm-match" key={flagTeam}>
                    <span className="tm-match-date">{lblText}</span>
                    <span className="tm-match-opp"><Flag team={flagTeam} />{tn(flagTeam)}</span>
                    <span className="tm-match-score">{p0(adv)}</span>
                    <span className="tm-match-pred">{t("tm_ko_split", { reg: p0(reg), et: p0(et) })}</span>
                  </span>
                );
                return (
                  <li key={k.round} className="tm-ko-known">
                    {side(t(lbl), team.team, k.advance, k.reg, k.et)}
                    {side("", k.opp, k.opp_advance, k.opp_reg, k.opp_et)}
                  </li>
                );
              }
              return (
                <li key={k.round}>
                  <span className="tm-match tm-match-proj">
                    <span className="tm-match-date">{t(lbl)}</span>
                    <span className="tm-match-opp"><Flag team={k.opp} />{tn(k.opp)}</span>
                    <span className="tm-match-pred">{t("tm_ko_note", { pct: p0(k.opp_share) })}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {history && history.dates && history.dates.length > 1 && (
        <>
          <h3>{t("tm_chart_h")}</h3>
          <TitleRaceChart history={history} highlight={team.team} tn={tn} />
        </>
      )}

      <h3>{t("tm_placement")}</h3>
      <p className="muted small">{t("tm_placement_hint")}</p>
      <PlacementHistogram
        values={positions}
        xLabel={t("tm_x_placement")}
        yLabel={t("tm_y_share")}
      />

      <h3>{t("tm_progress")}</h3>
      <Histogram bars={stages} xLabel={t("tm_x_round")} yLabel={t("tm_y_share")} />

      <h3>{t("tm_group_place")}</h3>
      {groupBars ? (
        <Histogram bars={groupBars} xLabel={t("tm_x_group")} yLabel={t("tm_y_share")} />
      ) : (
        <p className="muted">{t("tm_no_group")}</p>
      )}

      <h3>{t("tm_basis")}</h3>
      <div className="inputs-grid">
        <div className="input-card">
          <div className="input-head">{team.elo != null ? t("tm_elo") : t("tm_fifa")}</div>
          <div className="input-big">
            {team.elo != null ? Math.round(team.elo) : `${team.fifa_rating}p`}
          </div>
          <div className="muted small">
            {t("tm_fifa_rank", { r: team.fifa_field_rank })}
            {team.fifa_world_rank ? t("tm_world_rank", { r: team.fifa_world_rank }) : ""}
            {team.elo != null ? ` · FIFA ${team.fifa_rating}p` : ""}
          </div>
          {team.elo_delta != null && team.elo_delta !== 0 && (
            <div className={"input-delta " + (team.elo_delta > 0 ? "up" : "down")}>
              {t("tm_vs_week", { v: `${team.elo_delta > 0 ? "+" : ""}${Math.round(team.elo_delta)} Elo` })}
            </div>
          )}
        </div>
        <div className="input-card">
          <div className="input-head">{t("tm_books")}</div>
          <div className="input-big">{american(team.book_odds_avg)}</div>
          <div className="muted small">{t("tm_book_chance", { pct: pct(team.book_prob) })}</div>
          {team.book_prob_pct != null && team.book_prob_pct !== 0 && (
            <div className={"input-delta " + (team.book_prob_pct > 0 ? "up" : "down")}>
              {t("tm_vs_week", { v: `${team.book_prob_pct > 0 ? "+" : ""}${team.book_prob_pct}%` })}
            </div>
          )}
        </div>
        <div className="input-card">
          <div className="input-head">{t("tm_experts")}</div>
          <div className="input-big">{team.expert_mentions || 0}/{numExperts}</div>
          <div className="muted small">{t("tm_expert_weight", { pct: pct(team.expert_prob) })}</div>
        </div>
      </div>

      {books.length > 0 && (
        <>
          <h3>{t("tm_book_odds")}</h3>
          <div className="odds-row">
            {books.map(([book, o]) => (
              <span key={book} className="odds-chip">
                <b>{book}</b> {american(o)}
              </span>
            ))}
          </div>
        </>
      )}

      <h3>{t("tm_expert_preds")}</h3>
      {team.experts && team.experts.length > 0 ? (
        <ul className="expert-list">
          {team.experts.map((e, i) => (
            <li key={i}>
              <span className={`role role-${e.role}`}>{t(ROLE_KEY[e.role])}</span>
              {e.name}
              {e.outlet ? <span className="muted"> · {e.outlet}</span> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted small">{t("tm_no_experts", { n: numExperts })}</p>
      )}

      <div className="myteam-row">
        <button
          className={isMyTeam ? "ghost myteam-btn is-mine" : "primary myteam-btn"}
          onClick={() => onSetMyTeam(team.team)}
          disabled={isMyTeam}
        >
          {isMyTeam ? t("is_myteam") : <><Flag team={team.team} /> {t("set_myteam")}</>}
        </button>
      </div>
    </Modal>
  );
}
