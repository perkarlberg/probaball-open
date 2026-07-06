import { useState } from "react";
import { Flag } from "../flags.jsx";
import { useI18n } from "../i18n.jsx";

const pct = (v) => (v * 100).toFixed(1) + "%";

// Weekly change in champion probability, as signed percentage points (coloured).
function DeltaCell({ d }) {
  if (d == null) return <span className="muted">–</span>;
  const pp = d * 100;
  if (Math.abs(pp) < 0.05) return <span className="muted">–</span>;
  const up = pp > 0;
  return (
    <span className={up ? "delta up" : "delta down"}>
      {up ? "+" : "−"}{Math.abs(pp).toFixed(1)}%
    </span>
  );
}

// Probability columns. The 7-day delta is injected right after "champion".
const COLS = [
  { key: "champion", label: "col_champion", bar: true },
  { key: "final", label: "col_final" },
  { key: "semi", label: "col_semi" },
  { key: "quarter", label: "col_quarter" },
  { key: "r16", label: "col_r16" },
];

function ProbCell({ row, c }) {
  if (!c.bar) return pct(row[c.key]);
  return (
    <span className="cell-bar">
      <span className="cell-bar-fill" style={{ width: `${Math.min(100, row[c.key] * 100 * 3)}%` }} />
      <span className="cell-bar-text">{pct(row[c.key])}</span>
    </span>
  );
}

export default function Leaderboard({ teams, onTeamClick, expanded, onExpandChange }) {
  const { t, tn } = useI18n();
  const [localShowAll, setLocalShowAll] = useState(false);
  const showAll = expanded ?? localShowAll;
  const toggle = () => (onExpandChange ? onExpandChange(!showAll) : setLocalShowAll((s) => !s));
  const top = showAll ? teams : teams.slice(0, 10);
  // Only show the Δ column once the canonical carries trend data.
  const hasTrend = teams.some((r) => r.champion_delta != null);
  return (
    <>
    <div className="table-wrap">
      <table className="leaderboard">
        <thead>
          <tr>
            <th className="rank">#</th>
            <th>{t("col_team")}</th>
            <th className="num">{t("col_champion")}</th>
            {hasTrend && <th className="num" title={t("col_change_7d_hint")}>{t("col_change_7d")}</th>}
            {COLS.slice(1).map((c) => (
              <th key={c.key} className="num">{t(c.label)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {top.map((row, i) => (
            <tr
              key={row.team}
              className={"clickable" + (row.eliminated ? " eliminated" : "")}
              title={row.eliminated ? t("eliminated_hint") : undefined}
              onClick={() => onTeamClick(row.team)}
            >
              <td className="rank">{i + 1}</td>
              <td className="team">
                <button className="link">
                  <Flag team={row.team} />
                  {tn(row.team)}
                </button>
              </td>
              <td className="num"><ProbCell row={row} c={COLS[0]} /></td>
              {hasTrend && (
                <td className="num delta-cell"><DeltaCell d={row.champion_delta} /></td>
              )}
              {COLS.slice(1).map((c) => (
                <td key={c.key} className="num"><ProbCell row={row} c={c} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    <div className="show-all">
      <button className="ghost" onClick={toggle}>
        {showAll ? t("show_top10") : t("show_all", { n: teams.length })}
      </button>
    </div>
    </>
  );
}
