// Vertical-bar histogram with a real Y axis.
//   bars: [{label, value (0..1), highlight?}]  (X axis = placement)
//   Y axis = share of simulations (%), scaled to a "nice" max with gridlines.
const STEPS = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
const PLOT = 140; // px

const fmt = (v) => (v >= 0.1 ? (v * 100).toFixed(0) : (v * 100).toFixed(1)) + "%";

export default function Histogram({ bars, xLabel, yLabel }) {
  const max = Math.max(...bars.map((b) => b.value), 0.0001);
  // Headroom so the tallest bar stays ~<=85% of the plot, leaving room for its
  // value label above it without colliding with the axis caption.
  const niceMax = STEPS.find((s) => s >= max / 0.85) ?? 1;
  const ticks = [niceMax, niceMax / 2, 0];

  return (
    <div className="chart">
      {yLabel && <div className="y-caption">{yLabel}</div>}
      <div className="chart-row">
        <div className="y-axis" style={{ height: PLOT }}>
          {ticks.map((t) => (
            <span key={t}>{Math.round(t * 100)}%</span>
          ))}
        </div>
        <div className="plot" style={{ height: PLOT }}>
          <span className="grid" style={{ bottom: PLOT }} />
          <span className="grid" style={{ bottom: PLOT / 2 }} />
          <div className="bars">
            {bars.map((b) => {
              const h = Math.round((b.value / niceMax) * PLOT);
              return (
                <div key={b.label} className={"bar" + (b.highlight ? " hl" : "")}>
                  <span className="bar-val" style={{ bottom: h + 3 }}>
                    {fmt(b.value)}
                  </span>
                  <span className="bar-fill" style={{ height: Math.max(2, h) }} />
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div className="x-row">
        {bars.map((b) => (
          <span key={b.label} className="x-tick">
            {b.label}
          </span>
        ))}
      </div>
      {xLabel && <div className="axis-caption">{xLabel}</div>}
    </div>
  );
}
