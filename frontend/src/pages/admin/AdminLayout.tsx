import { useTranslation } from "react-i18next";
import { SectionLayout } from "@/components/layout/SectionLayout";

export function AdminLayout() {
  const { t } = useTranslation();
  return (
    <SectionLayout
      tabs={[
        { to: "/admin/settings", label: t("admin.appSettings") },
        { to: "/admin/wind", label: t("admin.windStations") },
        { to: "/admin/users", label: t("admin.users") },
        { to: "/admin/device-types", label: t("admin.deviceTypes") },
        { to: "/admin/boat-classes", label: t("admin.boatClasses") },
      ]}
    />
  );
}
