import { useTranslation } from "react-i18next";
import type { LegalDocByLang } from "@/content/legal/types";
import styles from "./legal.module.css";

/** Renders one legal document (Terms or Privacy) in the current UI language,
 * with an optional version/effective-date line. Shared by the standalone
 * /terms and /privacy pages and by the re-acceptance gate. */
export function LegalDocument({
  content,
  version,
  effectiveDate,
}: {
  content: LegalDocByLang;
  version?: string;
  effectiveDate?: string;
}) {
  const { t, i18n } = useTranslation();
  const doc = i18n.language === "it" ? content.it : content.en;

  return (
    <article className={styles.doc}>
      <h1 className={styles.title}>{doc.title}</h1>
      {(version || effectiveDate) && (
        <p className={styles.meta}>
          {version && t("legal.versionLabel", { version })}
          {version && effectiveDate && " · "}
          {effectiveDate && t("legal.effectiveLabel", { date: effectiveDate })}
        </p>
      )}
      {doc.lead && <p className={styles.lead}>{doc.lead}</p>}
      {doc.sections.map((section) => (
        <section key={section.title} className={styles.section}>
          <h2 className={styles.heading}>{section.title}</h2>
          {section.blocks.map((block, i) =>
            block.type === "ul" ? (
              <ul key={i} className={styles.list}>
                {(block.items ?? []).map((item, j) => (
                  <li key={j}>{item}</li>
                ))}
              </ul>
            ) : (
              <p key={i} className={styles.paragraph}>
                {block.text}
              </p>
            ),
          )}
        </section>
      ))}
    </article>
  );
}
