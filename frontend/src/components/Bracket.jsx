import { useI18n } from "../i18n.jsx";

// Map engine round names to localized labels (R32/R16 are universal).
const ROUND_KEY = { Kvartsfinal: "col_quarter", Semifinal: "col_semi", Final: "col_final" };

// Single-elimination bracket as left-to-right columns. Each round halves the
// field; the winner of each match is highlighted. Data is one sampled
// realisation from the engine (rounds[].matches[] = {a,b,ga,gb,winner,shootout}).
export default function Bracket({ bracket }) {
  const { t, tn } = useI18n();
  if (!bracket?.rounds?.length) return null;
  const podium = bracket.podium;
  const roundLabel = (r) => (ROUND_KEY[r] ? t(ROUND_KEY[r]) : r);
  return (
    <>
      {podium && (
        <div className="podium">
          <span className="medal gold">🥇 {tn(podium.gold)}</span>
          <span className="medal silver">🥈 {tn(podium.silver)}</span>
          <span className="medal bronze">🥉 {tn(podium.bronze)}</span>
        </div>
      )}
      <div className="bracket-scroll">
      <div className="bracket">
        {bracket.rounds.map((r) => (
          <div key={r.round} className="bracket-col">
            <div className="bracket-round-label">{roundLabel(r.round)}</div>
            <div className="bracket-matches">
              {r.matches.map((m, i) => (
                <Match key={i} m={m} tn={tn} />
              ))}
            </div>
          </div>
        ))}
        <div className="bracket-col champion-col">
          <div className="bracket-round-label">{t("col_champion")}</div>
          <div className="bracket-matches">
            <div className="champion-box">🏆 {tn(bracket.champion)}</div>
          </div>
        </div>
      </div>
      </div>
    </>
  );
}

function Match({ m, tn }) {
  return (
    <div className="match">
      <Side team={tn(m.a)} goals={m.ga} won={m.winner === m.a} />
      <Side team={tn(m.b)} goals={m.gb} won={m.winner === m.b} />
      {m.shootout && <span className="pen" title="pen">pen</span>}
    </div>
  );
}

function Side({ team, goals, won }) {
  return (
    <div className={"match-side" + (won ? " won" : "")}>
      <span className="match-team">{team}</span>
      <span className="match-goals">{goals}</span>
    </div>
  );
}
