import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { BoatClass, UUID } from "@/types";

const MAX_RESULTS = 30;

/** Type-to-filter combobox for picking a boat class out of a large catalog
 * (a plain <select> is unusable once the RYA catalog is loaded — 300+
 * options). Shows the selected class's logo + a few read-only details
 * below the input once picked. */
export function ClassPicker({
  label,
  id,
  classes,
  value,
  onChange,
}: {
  label: string;
  id: string;
  classes: BoatClass[];
  value: UUID | "";
  onChange: (id: UUID | "") => void;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const selected = classes.find((c) => c.id === value) ?? null;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = q ? classes.filter((c) => c.name.toLowerCase().includes(q)) : classes;
    return pool.slice(0, MAX_RESULTS);
  }, [classes, query]);

  const pick = (id: UUID | "") => {
    onChange(id);
    setQuery("");
    setOpen(false);
  };

  return (
    <div className="sf-field sf-combobox">
      <span className="sf-field__label">{label}</span>
      <input
        id={id}
        className="sf-field__input"
        autoComplete="off"
        value={open ? query : (selected?.name ?? "")}
        placeholder={t("common.search")}
        onFocus={() => setOpen(true)}
        onChange={(e) => setQuery(e.target.value)}
        // Delay so a click on an option (which blurs the input first) still registers.
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && (
        <div className="sf-combobox__list">
          <div className="sf-combobox__option sf-muted" onMouseDown={() => pick("")}>
            {t("boats.noClass")}
          </div>
          {filtered.length === 0 && (
            <div className="sf-combobox__option sf-muted">{t("boats.noClassMatch")}</div>
          )}
          {filtered.map((c) => (
            <div key={c.id} className="sf-combobox__option" onMouseDown={() => pick(c.id)}>
              {c.logo ? (
                <img className="sf-avatar sf-avatar--sm" src={c.logo.url} alt="" />
              ) : null}
              <span>{c.name}</span>
            </div>
          ))}
        </div>
      )}
      {!open && selected && <ClassInfo boatClass={selected} />}
    </div>
  );
}

/** Read-only summary strip for a selected class — secondary info, not part
 * of the boat's own fields, but useful context (e.g. confirming crew size
 * or PY rating match what the sailor expects). */
export function ClassInfo({ boatClass }: { boatClass: BoatClass }) {
  const { t } = useTranslation();
  const bits = [
    boatClass.hull_type && t(`admin.${boatClass.hull_type}`),
    boatClass.crew_size != null && `${t("admin.crewSize")}: ${boatClass.crew_size}`,
    boatClass.rig_type && t(`admin.${boatClass.rig_type}`),
    boatClass.py_rating != null && `PY ${boatClass.py_rating}`,
  ].filter(Boolean);

  if (bits.length === 0 && !boatClass.logo) return null;

  return (
    <div className="sf-classinfo">
      {boatClass.logo ? (
        <img className="sf-avatar sf-avatar--sm" src={boatClass.logo.url} alt="" />
      ) : null}
      {bits.length > 0 && <div className="sf-classinfo__details sf-muted">{bits.join(" · ")}</div>}
    </div>
  );
}
