import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { racesService } from "@/services/races.service";
import { useResource } from "@/hooks/useResource";
import { boatClassLabel, fmtShortDate } from "@/utils/format";
import { Spinner } from "@/components/ui/Spinner";
import type { RaceSummary, Regatta } from "@/types";

type SortMode = "newest" | "oldest" | "name";

export function RacesBrowser() {
  const { t } = useTranslation();
  const { data, loading, error } = useResource(
    () =>
      Promise.all([racesService.listRegattas(), racesService.listRaces()]).then(
        ([regattas, races]) => ({ regattas, races }),
      ),
    [],
  );
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortMode>("newest");

  const { regattas, orphans, racesByRegatta } = useMemo(() => {
    const byReg = new Map<string, RaceSummary[]>();
    const orphanRaces: RaceSummary[] = [];
    for (const r of data?.races ?? []) {
      if (r.regatta_id) {
        (byReg.get(r.regatta_id) ?? byReg.set(r.regatta_id, []).get(r.regatta_id)!).push(r);
      } else {
        orphanRaces.push(r);
      }
    }
    for (const arr of byReg.values())
      arr.sort((a, b) => (a.start_time ?? "").localeCompare(b.start_time ?? ""));
    orphanRaces.sort((a, b) => (b.start_time ?? "").localeCompare(a.start_time ?? ""));

    let regs = (data?.regattas ?? []).slice();
    const q = search.trim().toLowerCase();
    if (q) {
      regs = regs.filter((r) =>
        [r.name, r.venue, boatClassLabel(r.boat_class)]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(q),
      );
    }
    regs.sort((a, b) => {
      if (sort === "name") return (a.name ?? "").localeCompare(b.name ?? "");
      const aMost = byReg.get(a.regatta_id)?.at(-1)?.date ?? a.start_date;
      const bMost = byReg.get(b.regatta_id)?.at(-1)?.date ?? b.start_date;
      const cmp = (bMost ?? "").localeCompare(aMost ?? "");
      return sort === "oldest" ? -cmp : cmp;
    });
    return { regattas: regs, orphans: orphanRaces, racesByRegatta: byReg };
  }, [data, search, sort]);

  if (loading) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;

  return (
    <div className="sf-page">
      <h1 className="sf-page__title">{t("races.title")}</h1>
      <p className="sf-muted">{t("races.subtitle")}</p>

      <div className="sf-toolbar">
        <input
          className="sf-field__input"
          type="search"
          placeholder={t("races.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="sf-field__input"
          value={sort}
          onChange={(e) => setSort(e.target.value as SortMode)}
        >
          <option value="newest">{t("races.sortNewest")}</option>
          <option value="oldest">{t("races.sortOldest")}</option>
          <option value="name">{t("races.sortName")}</option>
        </select>
      </div>

      <h2 className="sf-section-title">{t("races.seriesTitle")}</h2>
      {regattas.length === 0 ? (
        <p className="sf-muted">{t("races.noSeries")}</p>
      ) : (
        <div className="sf-cardgrid">
          {regattas.map((r) => (
            <RegattaCard
              key={r.regatta_id}
              regatta={r}
              races={racesByRegatta.get(r.regatta_id) ?? []}
            />
          ))}
        </div>
      )}

      {orphans.length > 0 && (
        <>
          <h2 className="sf-section-title">{t("races.standalone")}</h2>
          <div className="sf-list">
            {orphans.map((r) => (
              <Link key={r.race_id} to={`/race/${r.race_id}`} className="sf-listrow">
                <span className="sf-listrow__meta">{fmtShortDate(r.date)}</span>
                <span className="sf-listrow__main">{r.name || "Race"}</span>
                <span className="sf-listrow__cta">{t("races.open")} →</span>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function RegattaCard({ regatta, races }: { regatta: Regatta; races: RaceSummary[] }) {
  const { t } = useTranslation();
  const cls = boatClassLabel(regatta.boat_class);
  const sub = [regatta.venue, cls, races.length ? t("races.raceCount", { count: races.length }) : null]
    .filter(Boolean)
    .join(" · ");
  const latest = races.length
    ? `${t("races.latest")}: ${races.at(-1)!.name || "Race"} · ${fmtShortDate(races.at(-1)!.date)}`
    : t("races.noRaces");

  return (
    <Link to={`/races/${regatta.regatta_id}`} className="sf-card sf-card--link">
      <div className="sf-card__name">{regatta.name}</div>
      {sub && <div className="sf-muted">{sub}</div>}
      <div className="sf-card__docs">
        {regatta.nor_url && <DocLink href={regatta.nor_url} label="NOR" />}
        {regatta.si_url && <DocLink href={regatta.si_url} label="SI" />}
        {regatta.website_url && <DocLink href={regatta.website_url} label="🌐" />}
      </div>
      <div className="sf-card__latest sf-muted">{latest}</div>
    </Link>
  );
}

function DocLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="sf-chip sf-chip--link"
      onClick={(e) => e.stopPropagation()}
    >
      {label}
    </a>
  );
}
