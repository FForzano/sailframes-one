import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { appConfigService, appConfigKeys } from "@/services/appConfig";
import { useToast } from "@/hooks/useToast";
import { Button } from "@/components/ui/Button";
import { InputField } from "@/components/ui/InputField";

export function AppSettingsPage() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: appConfigKeys.root, queryFn: appConfigService.get });
  const [minVersionAndroid, setMinVersionAndroid] = useState("");
  const [minVersionIos, setMinVersionIos] = useState("");

  useEffect(() => {
    if (config.data) {
      setMinVersionAndroid(config.data.min_native_version_android ?? "");
      setMinVersionIos(config.data.min_native_version_ios ?? "");
    }
  }, [config.data]);

  const update = useMutation({
    mutationFn: () =>
      appConfigService.update({
        min_native_version_android: minVersionAndroid.trim() || null,
        min_native_version_ios: minVersionIos.trim() || null,
      }),
    onSuccess: async () => {
      notify(t("common.saved"), "success");
      await queryClient.invalidateQueries({ queryKey: appConfigKeys.root });
    },
    onError: () => notify(t("errors.generic"), "error"),
  });

  return (
    <>
      <form
        className="sf-form__row"
        style={{ alignItems: "end" }}
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          update.mutate();
        }}
      >
        <InputField
          label={t("admin.minNativeVersionAndroid")}
          id="app-min-version-android"
          value={minVersionAndroid}
          onChange={(e) => setMinVersionAndroid(e.target.value)}
          placeholder="1.4.0"
        />
        <InputField
          label={t("admin.minNativeVersionIos")}
          id="app-min-version-ios"
          value={minVersionIos}
          onChange={(e) => setMinVersionIos(e.target.value)}
          placeholder="1.4.0"
        />
        <div className="sf-field">
          <Button type="submit" disabled={update.isPending}>
            {t("common.save")}
          </Button>
        </div>
      </form>
      <p className="sf-muted" style={{ marginTop: "0.5rem" }}>
        {t("admin.minNativeVersionHint")}
      </p>
    </>
  );
}
