import { useState } from "react";
import { track } from "../analytics.js";
import { useI18n } from "../i18n.jsx";

// "Decide a match" — the user picks a team that always beats another. Whenever
// that pairing occurs across the simulated runs, the chosen side wins. Stored
// as {a, b, winner} where a is the winner and b the opponent.
export default function ConvictionGames({ teams, forced, setForced, disabled }) {
  const { t, tn } = useI18n();
  const [winner, setWinner] = useState("");
  const [opp, setOpp] = useState("");

  const exists = (x, y) =>
    forced.some((f) => (f.a === x && f.b === y) || (f.a === y && f.b === x));

  function add() {
    if (!winner || !opp || winner === opp || exists(winner, opp)) return;
    setForced([...forced, { a: winner, b: opp, winner }]);
    track("add_conviction_game", { matchup: `${winner} vs ${opp}`, winner, loser: opp });
    setWinner("");
    setOpp("");
  }

  function remove(i) {
    setForced(forced.filter((_, idx) => idx !== i));
  }

  return (
    <div className="conviction">
      <div className="conviction-add">
        <select
          value={winner}
          onChange={(e) => setWinner(e.target.value)}
          disabled={disabled}
        >
          <option value="">{t("cv_winner_ph")}</option>
          {teams.map((tm) => (
            <option key={tm} value={tm} disabled={tm === opp}>
              {tn(tm)}
            </option>
          ))}
        </select>
        <span className="vs">{t("cv_beats")}</span>
        <select
          value={opp}
          onChange={(e) => setOpp(e.target.value)}
          disabled={disabled}
        >
          <option value="">{t("cv_opponent_ph")}</option>
          {teams.map((tm) => (
            <option key={tm} value={tm} disabled={tm === winner}>
              {tn(tm)}
            </option>
          ))}
        </select>
        <button
          className="ghost"
          onClick={add}
          disabled={disabled || !winner || !opp || winner === opp}
        >
          {t("cv_add")}
        </button>
      </div>

      {forced.length > 0 ? (
        <ul className="conviction-list">
          {forced.map((f, i) => (
            <li key={i}>
              <span className="loser">{tn(f.a === f.winner ? f.b : f.a)}</span>
              <span className="vs">→</span>
              <span className="winner">{t("cv_x_wins", { team: tn(f.winner) })}</span>
              <button className="link remove" onClick={() => remove(i)} disabled={disabled}>
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted small">{t("cv_empty")}</p>
      )}
    </div>
  );
}
