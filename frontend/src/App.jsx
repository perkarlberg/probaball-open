import { useEffect, useMemo, useState } from "react";
import { getCanonical, getMeta, simulate, rerollBracket, getHistory } from "./api.js";
import { track } from "./analytics.js";
import Controls from "./components/Controls.jsx";
import Leaderboard from "./components/Leaderboard.jsx";
import Groups from "./components/Groups.jsx";
import Bracket from "./components/Bracket.jsx";
import TeamModal from "./components/TeamModal.jsx";
import GroupModal from "./components/GroupModal.jsx";
import MatchModal from "./components/MatchModal.jsx";
import HowModal from "./components/HowModal.jsx";
import CodeModal from "./components/CodeModal.jsx";
import EvaluationModal from "./components/EvaluationModal.jsx";
import CountryCard from "./components/CountryCard.jsx";
import FAQ from "./components/FAQ.jsx";
import LangSwitcher from "./components/LangSwitcher.jsx";
import { teamForRegion } from "./flags.jsx";
import { teamForSlug, slugForTeam } from "./slugs.js";
import { useI18n, localizedPath, pathLang, stripLangPrefix } from "./i18n.jsx";

const DEFAULTS = { goal_scale: 0.0048, base_goals: 2.65, home_adv: 60, rho: -0.06 };

// Detect the visitor's nation from the browser locale region subtag
// (e.g. "es-MX" -> Mexico). Browser-config only; no external geo service.
function detectRegionTeam() {
  const langs = navigator.languages || [navigator.language || ""];
  for (const l of langs) {
    const region = l.split("-")[1];
    const team = teamForRegion(region);
    if (team) return team;
  }
  return null;
}

export default function App() {
  const [canonical, setCanonical] = useState(null);
  const [result, setResult] = useState(null);
  const [params, setParams] = useState(DEFAULTS);
  const [bounds, setBounds] = useState(null);
  const [isExperiment, setIsExperiment] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [teamSel, setTeamSel] = useState(null); // team name
  const [groupSel, setGroupSel] = useState(null); // group letter
  const [matchSel, setMatchSel] = useState(null); // { a, b } Swedish team keys
  const [forced, setForced] = useState([]); // conviction games
  const [showHow, setShowHow] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [showEval, setShowEval] = useState(false);
  const [titleHistory, setTitleHistory] = useState(null); // NB: not `history` — shadows window.history (go() uses it)
  const [theme, setTheme] = useState(
    () =>
      localStorage.getItem("theme") ||
      (window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark")
  );
  const { t, tn, lang, setLang } = useI18n();
  const [myTeam, setMyTeam] = useState(() => localStorage.getItem("myTeam") || "");
  const [expandTeams, setExpandTeams] = useState(false);
  const [trendOpen, setTrendOpen] = useState(false);

  useEffect(() => {
    if (myTeam) localStorage.setItem("myTeam", myTeam);
  }, [myTeam]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    (async () => {
      try {
        const [snap, m] = await Promise.all([getCanonical(), getMeta().catch(() => null)]);
        setCanonical(snap);
        setResult(snap);
        if (snap.params) setParams({ ...DEFAULTS, ...snap.params });
        if (m) setBounds(m.param_bounds);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  // Title-race history (per-team championship probability over time) powers the
  // charts in the Evaluation and team views. Fetched the first time either opens.
  useEffect(() => {
    if ((showEval || teamSel) && !titleHistory) getHistory().then(setTitleHistory).catch(() => {});
  }, [showEval, teamSel, titleHistory]);

  // Routing: real URLs /lag/<slug> and /grupp/<letter> drive the team/group
  // views; #sources / #how stay as hash overlays.
  useEffect(() => {
    const apply = () => {
      const raw = window.location.pathname;
      const urlLang = pathLang(raw);
      if (urlLang) setLang(urlLang); // a /<lang>/ URL forces that language
      const path = stripLangPrefix(raw);
      const mt = path.match(/^\/lag\/([^/]+)/);
      const mg = path.match(/^\/grupp\/([^/]+)/i);
      const mm = path.match(/^\/match\/([^/]+)/);
      setTeamSel(mt ? teamForSlug(mt[1]) : null);
      setGroupSel(mg ? mg[1].toUpperCase() : null);
      setShowEval(/^\/evaluation/.test(path));
      setShowCode(/^\/code/.test(path));
      if (mm) {
        const [hs, as] = mm[1].split("-vs-");
        setMatchSel({ a: teamForSlug(hs), b: teamForSlug(as) });
      } else {
        setMatchSel(null);
      }
      const h = window.location.hash.replace(/^#/, "");
      setShowHow(h === "how");
    };
    apply();
    window.addEventListener("popstate", apply);
    window.addEventListener("hashchange", apply);
    return () => {
      window.removeEventListener("popstate", apply);
      window.removeEventListener("hashchange", apply);
    };
  }, []);

  // Fast lookups for the modals + sorted team names for the controls.
  const teamByName = useMemo(() => {
    const map = {};
    (result?.teams || []).forEach((t) => (map[t.team] = t));
    return map;
  }, [result]);
  const teamNames = useMemo(
    () => (result?.teams || []).map((t) => t.team).sort((x, y) => x.localeCompare(y, "sv")),
    [result]
  );
  // Resolve a /match/ selection to the scheduled group fixture (+ its group).
  const matchInfo = useMemo(() => {
    const gm = result?.group_matches;
    if (!matchSel || !matchSel.a || !matchSel.b || !gm) return null;
    for (const g of Object.keys(gm)) {
      const m = gm[g].find((x) => x.home === matchSel.a && x.away === matchSel.b);
      if (m) return { match: m, group: g };
    }
    return null;
  }, [matchSel, result]);

  // The visitor's own nation: their chosen team, else locale-detected. + rank.
  const country = useMemo(() => {
    const name = myTeam || detectRegionTeam();
    if (!name) return null;
    const idx = (canonical?.teams || []).findIndex((x) => x.team === name);
    if (idx < 0) return null;
    return { team: canonical.teams[idx], rank: idx + 1 };
  }, [canonical, myTeam]);

  // Analytics: a team detail was opened (via click, deep link, or group modal).
  useEffect(() => {
    if (teamSel) track("view_team_detail", { team_name: teamSel });
  }, [teamSel]);

  async function runExperiment() {
    setBusy(true);
    setError(null);
    try {
      const r = await simulate({ ...params, forced });
      setResult(r);
      setIsExperiment(true);
      track("run_simulation", {
        goal_scale: params.goal_scale,
        base_goals: params.base_goals,
        home_adv: params.home_adv,
        conviction_games: forced.length,
        top_team: r?.top?.[0],
      });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function resetToCanonical() {
    setResult(canonical);
    setIsExperiment(false);
    if (canonical?.params) setParams({ ...DEFAULTS, ...canonical.params });
  }

  async function reroll() {
    setBusy(true);
    try {
      const b = await rerollBracket({ ...params, forced, top: result?.top });
      setResult((r) => ({ ...r, sample_bracket: b }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !result) {
    return (
      <div className="shell">
        <h1 className="brand">
          <img src="/logo.png" alt="Probaball" className="brand-logo" />
        </h1>
        <p className="error">{t("error_load", { error })}</p>
      </div>
    );
  }
  if (!result) {
    return (
      <div className="shell">
        <h1 className="brand">
          <img src="/logo.png" alt="Probaball" className="brand-logo" />
        </h1>
        <p className="lede">{t("lede_loading")}</p>
        <p className="muted loading-dots">{t("loading")}</p>
      </div>
    );
  }

  const model = result.model;
  // Navigate via real URLs; dispatch popstate so the route effect re-runs.
  const go = (path) => {
    history.pushState(null, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  };
  const scrollToSim = () =>
    document.getElementById("experiment")?.scrollIntoView({ behavior: "smooth" });
  const openTeam = (name) => go(localizedPath(`/lag/${slugForTeam(name)}/`, lang));
  const openGroup = (g) => go(localizedPath(`/grupp/${g.toLowerCase()}/`, lang));
  const openMatch = (homeSv, awaySv) =>
    go(localizedPath(`/match/${slugForTeam(homeSv)}-vs-${slugForTeam(awaySv)}/`, lang));
  const close = () => go(localizedPath("/", lang));
  const chooseMyTeam = (name) => {
    setMyTeam(name);
    close();
  };
  const changeMyTeam = () => {
    setExpandTeams(true);
    document.getElementById("leaderboard")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="shell">
      <header className="header-row">
        <div className="header-main">
        <h1 className="brand">
          <img src="/logo.png" alt="Probaball" className="brand-logo" />
        </h1>
        {isExperiment ? (
          <p className="lede">
            {t("lede_exp", {
              n: result.n?.toLocaleString(),
              forced: forced.length > 0 ? t("forced_suffix", { n: forced.length }) : "",
            })}
          </p>
        ) : (
          <div className="hero-lede">
            <p className="lede-head">{t("lede_head")}</p>
            <p className="lede-basis">
              {t("lede_basis_pre")}
              <strong className="lede-count">
                {t("lede_count", { n: result.n?.toLocaleString() })}
              </strong>
              {t("lede_basis_post")}
            </p>
            <p className="lede-cta">
              {t("lede_cta_pre")}
              <button className="link lede-cta-link" onClick={scrollToSim}>
                {t("lede_cta_link")}
              </button>
              {t("lede_cta_post")}
            </p>
          </div>
        )}
        <p className="muted small">
          <button className="link" onClick={() => go(localizedPath("/evaluation/", lang))}>
            {t("see_sources")}
          </button>
          {!isExperiment && result.date ? ` · ${t("basis_date", { date: result.date })}` : ""}
        </p>
        </div>
        {!isExperiment && (
          <CountryCard
            team={country?.team}
            rank={country?.rank}
            onOpen={openTeam}
            onChange={changeMyTeam}
          />
        )}
      </header>

      {error && <p className="error">{error}</p>}

      <section id="leaderboard">
        {!isExperiment && result.analysis && (() => {
          const a = result.analysis;
          // New shape: summary (always shown) + detail (expandable). Fall back to
          // the legacy single `text` field for snapshots baked before the split.
          const lede = a.summary || a.text;
          const summary = lede && (lede[lang] || lede.en);
          const detail = a.detail && (a.detail[lang] || a.detail.en);
          if (!summary) return null;
          return (
            <div className="trend-block">
              <h3 className="trend-head">{t("trend_label")}</h3>
              <p className="trend-text">{summary}</p>
              {detail && trendOpen && <p className="trend-text trend-detail">{detail}</p>}
              {detail && (
                <button type="button" className="trend-more"
                  aria-expanded={trendOpen} onClick={() => setTrendOpen((o) => !o)}>
                  {t(trendOpen ? "read_less" : "read_more")}
                </button>
              )}
            </div>
          );
        })()}
        <h2>{t("sec_champion")}</h2>
        <p className="muted small">{t("hint_team")}</p>
        <Leaderboard
          teams={result.teams}
          onTeamClick={openTeam}
          expanded={expandTeams}
          onExpandChange={setExpandTeams}
        />
      </section>

      <section>
        <h2>{t("sec_groups")}</h2>
        <p className="muted small">{t("hint_group")}</p>
        <Groups groups={result.groups} onGroupClick={openGroup} />
        <p className="muted small">{t("groups_legend")}</p>
      </section>

      <section className="bracket-section">
        <div className="section-head">
          <h2>{t("sec_bracket")}</h2>
          <button className="ghost" onClick={reroll} disabled={busy}>
            {t("reroll")}
          </button>
        </div>
        <p className="muted small">{t("bracket_help")}</p>
        <Bracket bracket={result.sample_bracket} />
      </section>

      <section id="experiment">
        <h2>{t("sec_experiment")}</h2>
        <p className="muted small">{t("experiment_hint")}</p>
        <Controls
          params={params}
          setParams={setParams}
          bounds={bounds}
          defaults={DEFAULTS}
          onRun={runExperiment}
          onReset={resetToCanonical}
          isExperiment={isExperiment}
          busy={busy}
          teams={teamNames}
          forced={forced}
          setForced={setForced}
        />
      </section>

      <FAQ teams={result.teams} model={model} />

      <footer>
        <div className="footer-left">
          <button className="link" onClick={() => go(localizedPath("/", lang) + "#how")}>
            {t("how_link")}
          </button>
          <button className="link" onClick={() => go(localizedPath("/evaluation/", lang))}>
            {t("eval_link")}
          </button>
          <button className="link" onClick={() => go(localizedPath("/code/", lang))}>
            {t("code_link")}
          </button>
        </div>
        <div className="footer-right">
          <LangSwitcher />
          <button
            className="ghost theme-toggle"
            onClick={() => setTheme((cur) => (cur === "dark" ? "light" : "dark"))}
            aria-label="theme"
          >
            {theme === "dark" ? t("theme_day") : t("theme_night")}
          </button>
        </div>
      </footer>

      {teamSel && teamByName[teamSel] && (
        <TeamModal
          team={teamByName[teamSel]}
          groupRow={(result.groups[teamByName[teamSel].group] || []).find(
            (r) => r.team === teamSel
          )}
          matches={(result.group_matches?.[teamByName[teamSel].group] || [])
            .filter((m) => m.home === teamSel || m.away === teamSel)
            .slice()
            .sort((a, b) => a.date.localeCompare(b.date))}
          history={titleHistory}
          onMatchClick={openMatch}
          isMyTeam={myTeam === teamSel}
          onSetMyTeam={chooseMyTeam}
          numExperts={model?.num_experts}
          onClose={close}
        />
      )}
      {groupSel && result.groups[groupSel] && (
        <GroupModal
          group={groupSel}
          rows={result.groups[groupSel]}
          matches={result.group_matches?.[groupSel]}
          onTeamClick={openTeam}
          onMatchClick={openMatch}
          onClose={close}
        />
      )}
      {matchInfo && (
        <MatchModal
          match={matchInfo.match}
          group={matchInfo.group}
          onTeamClick={openTeam}
          onGroupClick={openGroup}
          onClose={close}
        />
      )}
      {showHow && <HowModal model={model} onClose={close} />}
      {showCode && <CodeModal onClose={close} />}
      {showEval && (
        <EvaluationModal
          data={canonical?.evaluation}
          date={canonical?.date}
          model={model}
          history={titleHistory}
          onMatchClick={openMatch}
          onClose={close}
        />
      )}
    </div>
  );
}
