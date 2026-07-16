import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { devicesService, deviceKeys } from "@/services/devices";
import { useToast } from "@/hooks/useToast";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { InputField } from "@/components/ui/InputField";
import type { UUID } from "@/types";

export function DeviceTypesPage() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", category: "boat_tracker", parser_key: "" });

  const types = useQuery({ queryKey: deviceKeys.types, queryFn: devicesService.listTypes });
  const create = useMutation({
    mutationFn: () => devicesService.createType(form),
    onSuccess: async () => {
      setForm({ name: "", category: "boat_tracker", parser_key: "" });
      await queryClient.invalidateQueries({ queryKey: deviceKeys.types });
    },
    onError: () => notify(t("errors.generic"), "error"),
  });
  const remove = useMutation({
    mutationFn: (id: UUID) => devicesService.removeType(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: deviceKeys.types }),
    onError: () => notify(t("errors.generic"), "error"),
  });

  return (
    <Card title={t("admin.deviceTypes")}>
      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th>{t("common.name")}</th>
              <th>{t("admin.category")}</th>
              <th>{t("admin.parserKey")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {types.data?.map((dt) => (
              <tr key={dt.id}>
                <td>{dt.name}</td>
                <td>{dt.category}</td>
                <td className="sf-muted">{dt.parser_key}</td>
                <td>
                  <Button variant="danger" className="sf-btn--sm" onClick={() => remove.mutate(dt.id)}>
                    ×
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form
        className="sf-form__row"
        style={{ alignItems: "end", marginTop: "0.75rem" }}
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <InputField
          label={t("common.name")}
          id="dt-name"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          required
        />
        <Select
          label={t("admin.category")}
          id="dt-cat"
          value={form.category}
          onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
        >
          <option value="boat_tracker">boat_tracker</option>
          <option value="wearable">wearable</option>
          <option value="wind_station">wind_station</option>
        </Select>
        <InputField
          label={t("admin.parserKey")}
          id="dt-parser"
          value={form.parser_key}
          onChange={(e) => setForm((f) => ({ ...f, parser_key: e.target.value }))}
          placeholder="e1_csv_v1"
          required
        />
        <div className="sf-field">
          <Button type="submit" disabled={create.isPending || !form.name || !form.parser_key}>
            {t("common.add")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
