import { useTranslation } from "react-i18next";
import {
  BOM_COMMON,
  BOM_OPTION_A,
  BOM_OPTION_B,
  BOM_OPTIONAL,
  BOM_TOTALS,
  type BomGroup,
} from "@/data/bom";

// Static hardware BOM reference (ported from legacy bom.html).
export function Bom() {
  const { t } = useTranslation();
  return (
    <div className="sf-page">
      <h1 className="sf-page__title">{t("bom.title")}</h1>
      <p className="sf-muted">{t("bom.subtitle")}</p>

      <BomTable group={BOM_COMMON} />
      <BomTable group={BOM_OPTION_A} />
      <BomTable group={BOM_OPTION_B} />
      <BomTable group={BOM_OPTIONAL} />

      <h2 className="sf-section-title">{t("bom.totals")}</h2>
      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th>{t("bom.configuration")}</th>
              <th>{t("bom.hardwareTotal")}</th>
            </tr>
          </thead>
          <tbody>
            {BOM_TOTALS.map((r) => (
              <tr key={r.config}>
                <td>{r.config}</td>
                <td>{r.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sf-muted sf-mt">{t("bom.fleetNote")}</p>
    </div>
  );
}

function BomTable({ group }: { group: BomGroup }) {
  const { t } = useTranslation();
  return (
    <>
      <h2 className="sf-section-title">
        {t(`bom.groups.${group.key}`)}
        {group.subtotal && <span className="sf-muted"> · {group.subtotal}</span>}
      </h2>
      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th>#</th>
              <th>{t("bom.part")}</th>
              <th>{t("bom.qty")}</th>
              <th>{t("bom.price")}</th>
              <th>{t("bom.source")}</th>
            </tr>
          </thead>
          <tbody>
            {group.parts.map((p) => (
              <tr key={p.ref}>
                <td>{p.ref}</td>
                <td>{p.part}</td>
                <td>{p.qty}</td>
                <td>{p.price}</td>
                <td>{p.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
