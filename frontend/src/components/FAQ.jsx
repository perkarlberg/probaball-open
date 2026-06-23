import { useI18n } from "../i18n.jsx";

// Vanliga frågor — also mirrored as FAQPage JSON-LD in index.html for search
// engines and AI answer engines (Swedish there; UI localizes per visitor).
export default function FAQ({ teams, model }) {
  const { t, tn } = useI18n();
  const top = (teams || []).slice(0, 3);
  const fav = top[0] ? tn(top[0].team) : "";
  const second = top[1] ? tn(top[1].team) : "";
  const third = top[2] ? tn(top[2].team) : "";
  const favPct = teams?.[0] ? (teams[0].champion * 100).toFixed(1) + " %" : "";
  const books = model?.books?.join(", ") || "—";
  const n = model?.num_experts || 18;

  const items = [
    { q: t("faq_q1"), a: t("faq_a1", { n }) },
    { q: t("faq_q2"), a: t("faq_a2", { fav, second, third, favPct }) },
    { q: t("faq_q3"), a: t("faq_a3", { books, n }) },
    { q: t("faq_q4"), a: t("faq_a4") },
    { q: t("faq_q6"), a: t("faq_a6") },
    { q: t("faq_q5"), a: t("faq_a5") },
  ];

  return (
    <section>
      <h2>{t("sec_faq")}</h2>
      <div className="faq">
        {items.map((it, i) => (
          <details key={i} className="faq-item" open={i === 0}>
            <summary>{it.q}</summary>
            <p>{it.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
