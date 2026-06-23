import Modal from "./Modal.jsx";
import { useI18n } from "../i18n.jsx";

// Public GitHub mirror of the model + this app. Kept in sync from the
// (private) dev repo by publish.sh.
export const REPO_URL = "https://github.com/perkarlberg/probaball-open";

// "Open source" page: explains that the whole forecast is open and links to
// the repo. Shown as an overlay on the /code route.
export default function CodeModal({ onClose }) {
  const { t } = useI18n();
  return (
    <Modal title={t("code_title")} subtitle={t("code_subtitle")} onClose={onClose}>
      <p className="small">{t("code_lede")}</p>

      <p>
        <a className="btn repo-link" href={REPO_URL} target="_blank" rel="noopener noreferrer">
          {t("code_cta")}
        </a>
      </p>

      <h3>{t("code_what_h")}</h3>
      <ul className="how-list">
        <li>{t("code_what_data")}</li>
        <li>{t("code_what_model")}</li>
        <li>{t("code_what_backtest")}</li>
        <li>{t("code_what_web")}</li>
      </ul>

      <h3>{t("code_data_h")}</h3>
      <p className="muted small">{t("code_data")}</p>
    </Modal>
  );
}
