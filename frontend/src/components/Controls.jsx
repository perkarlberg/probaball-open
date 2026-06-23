import ConvictionGames from "./ConvictionGames.jsx";
import { useI18n } from "../i18n.jsx";

// Parameter sliders for hypothesis testing. N is fixed (1000) on the server,
// so it is shown but not adjustable.
// `neg` fields display the negated param value: the engine's rho is negative
// for more draws, but the slider reads as a positive "draw tendency".
const FIELDS = [
  { key: "goal_scale", label: "ctrl_goal_scale", hint: "ctrl_goal_scale_hint", step: 0.0002, fmt: (v) => v.toFixed(4) },
  { key: "base_goals", label: "ctrl_base_goals", hint: "ctrl_base_goals_hint", step: 0.05, fmt: (v) => v.toFixed(2) },
  { key: "home_adv", label: "ctrl_home_adv", hint: "ctrl_home_adv_hint", step: 5, fmt: (v) => Math.round(v) },
  { key: "rho", label: "ctrl_rho", hint: "ctrl_rho_hint", step: 0.01, neg: true, fmt: (v) => v.toFixed(2) },
];

export default function Controls({
  params,
  setParams,
  bounds,
  defaults,
  onRun,
  onReset,
  isExperiment,
  busy,
  teams,
  forced,
  setForced,
}) {
  const { t } = useI18n();
  function update(key, value) {
    setParams((p) => ({ ...p, [key]: value }));
  }

  return (
    <div className="controls">
      <div className="controls-subhead">{t("ctrl_params")}</div>
      <div className="controls-grid">
        {FIELDS.map((f) => {
          const [rawLo, rawHi] = bounds?.[f.key] ?? [0, params[f.key] * 2 || 1];
          // For `neg` fields the slider operates on the negated value.
          const lo = f.neg ? -rawHi : rawLo;
          const hi = f.neg ? -rawLo : rawHi;
          const dispVal = f.neg ? -params[f.key] : params[f.key];
          return (
            <label key={f.key} className="control">
              <span className="control-label">
                {t(f.label)}
                <span className="control-value">{f.fmt(dispVal)}</span>
              </span>
              <input
                type="range"
                min={lo}
                max={hi}
                step={f.step}
                value={dispVal}
                onChange={(e) => {
                  const v = parseFloat(e.target.value);
                  update(f.key, f.neg ? -v : v);
                }}
              />
              <span className="control-hint">{t(f.hint)}</span>
            </label>
          );
        })}
      </div>

      <div className="controls-subhead">
        {t("ctrl_conviction")}
        <span className="muted small">{t("ctrl_conviction_hint")}</span>
      </div>
      <ConvictionGames
        teams={teams}
        forced={forced}
        setForced={setForced}
        disabled={busy}
      />

      <div className="controls-actions">
        <button className="primary" onClick={onRun} disabled={busy}>
          {busy ? t("ctrl_running") : t("ctrl_run")}
        </button>
        <button
          className="ghost"
          onClick={() => setParams({ ...defaults })}
          disabled={busy}
        >
          {t("ctrl_reset")}
        </button>
        {isExperiment && (
          <button className="ghost" onClick={onReset} disabled={busy}>
            {t("ctrl_back")}
          </button>
        )}
      </div>
    </div>
  );
}
