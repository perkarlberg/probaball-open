// Title-race line chart: each team's championship probability over time, from
// /api/history. Pure SVG (no chart dependency), matching CalibrationChart.
// - no `highlight`: colour the top `top` teams (clean palette), label all.
// - `highlight` (Swedish team key): that team is bold/coloured, the rest are
//   muted context — used in the team view.
const W = 640, H = 360;
const ML = 34, MR = 96, MT = 16, MB = 26;
const PW = W - ML - MR, PH = H - MT - MB;

const PALETTE = ["#e15759", "#4e79a7", "#59a14f", "#f28e2b", "#b07aa1",
                 "#76b7b2", "#ff9da7", "#c9a227", "#9c755f", "#4b6584"];
const MUTED = "#c7cad0";

const fmtDate = (iso) => {
  const [, m, d] = iso.split("-");
  return `${+m}/${+d}`;
};

export default function TitleRaceChart({ history, highlight = null, top = 10, tn }) {
  const dates = history?.dates || [];
  const teams = history?.teams || [];
  if (dates.length < 2 || !teams.length) return null;
  const name = (t) => (tn ? tn(t.team) : t.name_en || t.team);

  // Which teams to draw.
  let shown = teams.slice(0, top);
  if (highlight && !shown.some((t) => t.team === highlight)) {
    const h = teams.find((t) => t.team === highlight);
    if (h) shown = [h, ...teams.slice(0, top - 1)];
  }

  const n = dates.length;
  const x = (i) => ML + (n > 1 ? i / (n - 1) : 0.5) * PW;
  const vals = shown.flatMap((t) => t.champion.map((v) => (v || 0) * 100));
  const ymax = Math.max(5, Math.ceil(Math.max(...vals) / 5) * 5);
  const y = (v) => MT + (1 - v / ymax) * PH;

  const color = (t, i) =>
    highlight ? (t.team === highlight ? "#4e79a7" : MUTED) : PALETTE[i % PALETTE.length];
  const isLead = (t) => !highlight || t.team === highlight;

  // Right-side labels, de-collided.
  const labels = shown
    .map((t, i) => ({
      y: y((t.champion[n - 1] || 0) * 100),
      c: color(t, i),
      txt: name(t),
      lead: highlight ? t.team === highlight : true,
    }))
    .sort((a, b) => a.y - b.y);
  const gap = 13;
  for (let j = 1; j < labels.length; j++)
    if (labels[j].y - labels[j - 1].y < gap) labels[j].y = labels[j - 1].y + gap;

  const yticks = [0, ymax / 2, ymax];
  const xticks = [0, Math.floor((n - 1) / 2), n - 1];

  return (
    <div className="trace">
      <svg viewBox={`0 0 ${W} ${H}`} className="trace-svg" role="img" aria-label="title race">
        {yticks.map((tk) => (
          <g key={tk}>
            <line className="calib-grid" x1={ML} y1={y(tk)} x2={ML + PW} y2={y(tk)} />
            <text className="calib-tick" x={ML - 6} y={y(tk) + 3} textAnchor="end">{tk}%</text>
          </g>
        ))}
        {xticks.map((i) => (
          <text key={i} className="calib-tick" x={x(i)} y={H - 8} textAnchor="middle">
            {fmtDate(dates[i])}
          </text>
        ))}
        {shown.map((t, i) => (
          <polyline
            key={t.team}
            className="trace-line"
            points={t.champion.map((v, k) => `${x(k)},${y((v || 0) * 100)}`).join(" ")}
            fill="none"
            stroke={color(t, i)}
            strokeWidth={isLead(t) ? 2.6 : 1.3}
            opacity={isLead(t) ? 1 : 0.75}
          />
        ))}
        {labels.map((l, i) => (
          <text key={i} x={ML + PW + 5} y={l.y + 3} fill={l.c}
            fontSize={l.lead ? 12 : 10.5} fontWeight={l.lead ? 600 : 400}>
            {l.txt}
          </text>
        ))}
      </svg>
    </div>
  );
}
