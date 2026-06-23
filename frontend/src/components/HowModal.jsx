import Modal from "./Modal.jsx";
import { useI18n } from "../i18n.jsx";

// Plain-language explanation of how the model works.
export default function HowModal({ model, onClose }) {
  const { t } = useI18n();
  const books = model?.books?.join(", ") || "—";
  const nExperts = model?.num_experts || 18;
  return (
    <Modal title={t("hm_title")} subtitle={t("hm_subtitle")} onClose={onClose}>
      <h3>{t("hm_h_idea")}</h3>
      <p className="small">{t("hm_idea")}</p>

      <h3>{t("hm_h_strength")}</h3>
      <p className="small">{t("hm_strength")}</p>
      <ul className="how-list">
        <li>{t("hm_li_fifa")}</li>
        <li>{t("hm_li_books", { books })}</li>
        <li>{t("hm_li_experts", { n: nExperts })}</li>
      </ul>
      <p className="small">{t("hm_blend")}</p>

      <h3>{t("hm_h_match")}</h3>
      <p className="small">{t("hm_match")}</p>

      <h3>{t("hm_h_conviction")}</h3>
      <p className="small">{t("hm_conviction")}</p>

      <h3>{t("hm_h_note")}</h3>
      <p className="muted small">{t("hm_note")}</p>
    </Modal>
  );
}
