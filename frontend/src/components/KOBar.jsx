import { Flag } from "../flags.jsx";
import { useI18n } from "../i18n.jsx";

const p0 = (v) => Math.round(v * 100) + "%";

// Knockout "who advances" bar (Option A): four segments
//   [home win 90' | home win ET/pens | away win ET/pens | away win 90']
// Colour = team; hatched = decided in extra time / penalties. The blue->red
// colour change between the two hatched middle segments IS the advance line, so
// each team's total advance % (the two segments on its side) reads off the ends.
export default function KOBar({ home, away, hReg, hEt, aEt, aReg }) {
  const { t, tn } = useI18n();
  const hAdv = hReg + hEt, aAdv = aEt + aReg;
  const seg = (cls, w, who, kind) =>
    w > 0 ? <span className={"ko-seg " + cls} style={{ width: p0(w) }}
                  title={`${tn(who)} ${p0(w)} · ${t(kind)}`} /> : null;
  return (
    <div className="ko-pred">
      <div className="ko-ends">
        <span className="ko-end"><Flag team={home} />&nbsp;{tn(home)}&nbsp;<b>{p0(hAdv)}</b></span>
        <span className="ko-end"><b>{p0(aAdv)}</b>&nbsp;{tn(away)}&nbsp;<Flag team={away} /></span>
      </div>
      <div className="ko-bar" role="img"
           aria-label={`${tn(home)} ${p0(hAdv)}, ${tn(away)} ${p0(aAdv)}`}>
        {seg("h-reg", hReg, home, "ko_reg_lbl")}
        {seg("h-et", hEt, home, "ko_et_lbl")}
        {seg("a-et", aEt, away, "ko_et_lbl")}
        {seg("a-reg", aReg, away, "ko_reg_lbl")}
      </div>
      <div className="ko-legend small muted">
        <span><i className="ko-key solid" /> {t("ko_reg_lbl")}</span>
        <span><i className="ko-key hatch" /> {t("ko_et_lbl")}</span>
      </div>
    </div>
  );
}
