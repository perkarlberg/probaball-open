// Histogram over final placement 1..48 (numeric X axis), Y = share of sims.
// Teams eliminated in the same round share a position range, so each round's
// probability is spread evenly across its positions (e.g. the two semifinal
// losers -> places 3-4). values must already be the per-position shares.
const STEPS = [0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0];
const PLOT = 140;

export default function PlacementHistogram({ values, xLabel, yLabel, xticks }) {
  const n = values.length;
  const max = Math.max(...values, 0.0001);
  const niceMax = STEPS.find((s) => s >= max / 0.85) ?? 1;
  const yticks = [niceMax, niceMax / 2, 0];
  const labelAt = xticks || [1, 8, 16, 24, 32, 40, n];

  return (
    <div className="chart">
      {yLabel && <div className="y-caption">{yLabel}</div>}
      <div className="chart-row">
        <div className="y-axis" style={{ height: PLOT }}>
          {yticks.map((t) => (
            <span key={t}>{Math.round(t * 100)}%</span>
          ))}
        </div>
        <div className="plot" style={{ height: PLOT }}>
          <span className="grid" style={{ bottom: PLOT }} />
          <span className="grid" style={{ bottom: PLOT / 2 }} />
          <div className="pbars">
            {values.map((v, i) => (
              <span
                key={i}
                className={"pbar" + (i === 0 ? " hl" : "")}
                style={{ height: Math.max(1, Math.round((v / niceMax) * PLOT)) }}
                title={`Placering ${i + 1}: ${(v * 100).toFixed(1)}%`}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="px-row">
        {Array.from({ length: n }, (_, i) => (
          <span key={i} className="px-cell">
            {labelAt.includes(i + 1) ? i + 1 : ""}
          </span>
        ))}
      </div>
      {xLabel && <div className="axis-caption">{xLabel}</div>}
    </div>
  );
}
