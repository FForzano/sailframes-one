import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import type { BoatClass, UUID } from "@/types";

const MAX_RESULTS = 30;

function classInfoBits(boatClass: BoatClass, t: (key: string) => string): string[] {
  return [
    boatClass.hull_type && t(`admin.${boatClass.hull_type}`),
    boatClass.crew_size != null && `${t("admin.crewSize")}: ${boatClass.crew_size}`,
    boatClass.rig_type && t(`admin.${boatClass.rig_type}`),
    boatClass.py_rating != null && `PY ${boatClass.py_rating}`,
  ].filter((b): b is string => Boolean(b));
}

/** Type-to-filter combobox for picking a boat class out of a large catalog
 * (a plain <select> is unusable once the RYA catalog is loaded — 300+
 * options). Once a class is picked, collapses to a single read-only card
 * (logo + name + details, all in one block) with an edit icon that reopens
 * the search input — instead of leaving an always-editable field sitting
 * in the form. */
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
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = classes.find((c) => c.id === value) ?? null;

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = q ? classes.filter((c) => c.name.toLowerCase().includes(q)) : classes;
    return pool.slice(0, MAX_RESULTS);
  }, [classes, query]);

  const pick = (id: UUID | "") => {
    onChange(id);
    setQuery("");
    setOpen(false);
    setEditing(false);
  };

  if (selected && !editing) {
    const bits = classInfoBits(selected, t);
    return (
      <div className="sf-field">
        <span className="sf-field__label">{label}</span>
        <div className="sf-strip__item sf-strip__item--muted">
          <span style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            {selected.logo && (
              <img className="sf-avatar sf-avatar--sm" src={selected.logo.url} alt="" />
            )}
            <span>
              <strong>{selected.name}</strong>
              {bits.length > 0 && <div className="sf-classinfo__details sf-muted">{bits.join(" · ")}</div>}
            </span>
          </span>
          <Button
            variant="ghost"
            className="sf-btn--sm"
            type="button"
            aria-label={t("common.edit")}
            title={t("common.edit")}
            onClick={() => setEditing(true)}
          >
            ✎
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="sf-field sf-combobox">
      <span className="sf-field__label">{label}</span>
      <input
        ref={inputRef}
        id={id}
        className="sf-field__input"
        autoComplete="off"
        value={open ? query : (selected?.name ?? "")}
        placeholder={t("common.search")}
        onFocus={() => setOpen(true)}
        onChange={(e) => setQuery(e.target.value)}
        onBlur={() =>
          // Delay so a click on an option (which blurs the input first) still registers.
          setTimeout(() => {
            setOpen(false);
            setEditing(false);
          }, 150)
        }
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
    </div>
  );
}

/** Read-only summary strip for a selected class — secondary info, not part
 * of the boat's own fields, but useful context (e.g. confirming crew size
 * or PY rating match what the sailor expects). Used outside ClassPicker
 * (e.g. the non-manager read-only boat view). */
export function ClassInfo({ boatClass }: { boatClass: BoatClass }) {
  const { t } = useTranslation();
  const bits = classInfoBits(boatClass, t);

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
