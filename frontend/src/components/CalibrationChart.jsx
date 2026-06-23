// Reliability diagram: predicted probability (x) vs observed frequency (y).
// The diagonal is perfect calibration; each dot is one probability bin, its
// area ∝ the number of (outcome) observations that fell in it. Pure SVG so it
// prerenders for crawlers and needs no chart dependency.
const W = 260, H = 260;
const ML = 36, MR = 12, MT = 12, MB = 30;
const PW = W - ML - MR, PH = H - MT - MB;
const x = (p) => ML + p * PW;
const y = (v) => MT + (1 - v) * PH;
const TICKS = [0, 0.25, 0.5, 0.75, 1];

export default function CalibrationChart({ bins, xLabel, yLabel, idealLabel, modelLabel }) {
  const pts = (bins || []).filter((b) => b.n > 0 && b.mean_pred != null);
  const maxN = Math.max(1, ...pts.map((b) => b.n));
  const r = (n) => 3 + 6 * Math.sqrt(n / maxN);

  return (
    <div className="calib">
      <svg viewBox={`0 0 ${W} ${H}`} className="calib-svg" role="img"
        aria-label={`${xLabel} / ${yLabel}`}>
        {/* gridlines + axis ticks */}
        {TICKS.map((tk) => (
          <g key={tk}>
            <line className="calib-grid" x1={x(tk)} y1={y(0)} x2={x(tk)} y2={y(1)} />
            <line className="calib-grid" x1={x(0)} y1={y(tk)} x2={x(1)} y2={y(tk)} />
            <text className="calib-tick" x={x(tk)} y={y(0) + 14} textAnchor="middle">
              {Math.round(tk * 100)}
            </text>
            <text className="calib-tick" x={ML - 6} y={y(tk) + 3} textAnchor="end">
              {Math.round(tk * 100)}
            </text>
          </g>
        ))}
        {/* perfect-calibration diagonal */}
        <line className="calib-ideal" x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} />
        {/* model points */}
        {pts.map((b) => (
          <circle key={b.lo} className="calib-pt" cx={x(b.mean_pred)} cy={y(b.obs)} r={r(b.n)}>
            <title>{`${Math.round(b.mean_pred * 100)}% predicted → ${Math.round(b.obs * 100)}% observed (n=${b.n})`}</title>
          </circle>
        ))}
        <text className="calib-axis" x={ML + PW / 2} y={H - 2} textAnchor="middle">{xLabel}</text>
        <text className="calib-axis" transform={`translate(10 ${MT + PH / 2}) rotate(-90)`}
          textAnchor="middle">{yLabel}</text>
      </svg>
      <div className="calib-legend">
        <span><i className="calib-key-ideal" />{idealLabel}</span>
        <span><i className="calib-key-pt" />{modelLabel}</span>
      </div>
    </div>
  );
}
