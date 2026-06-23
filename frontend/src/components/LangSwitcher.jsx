import { LANGS, useI18n, localizedPath } from "../i18n.jsx";

export default function LangSwitcher() {
  const { lang, setLang, t } = useI18n();
  // Switching language navigates to the prefixed URL for the current page, so
  // the address bar, hreflang and language state all stay in sync.
  const choose = (next) => {
    const url = localizedPath(window.location.pathname, next) + window.location.hash;
    history.pushState(null, "", url);
    window.dispatchEvent(new PopStateEvent("popstate"));
    setLang(next);
  };
  return (
    <select
      className="lang-switcher"
      value={lang}
      onChange={(e) => choose(e.target.value)}
      aria-label={t("lang_label")}
    >
      {Object.entries(LANGS).map(([code, name]) => (
        <option key={code} value={code}>
          {name}
        </option>
      ))}
    </select>
  );
}
