import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { usersService, userKeys } from "@/services/users";
import { userLabel } from "@/utils/format";

export function UsersPage() {
  const { t } = useTranslation();
  const users = useQuery({ queryKey: userKeys.all, queryFn: usersService.list });
  return (
    <div className="sf-tablewrap">
      <table className="sf-table">
        <thead>
          <tr>
            <th>{t("common.name")}</th>
            <th>{t("auth.email")}</th>
            <th>{t("common.status")}</th>
            <th>{t("admin.superadmin")}</th>
          </tr>
        </thead>
        <tbody>
          {users.data?.map((u) => (
            <tr key={u.id}>
              <td>{userLabel(u)}</td>
              <td className="sf-muted">{u.email}</td>
              <td>
                <span
                  className={
                    u.status === "active" ? "sf-badge sf-badge--success" : "sf-badge sf-badge--danger"
                  }
                >
                  {u.status}
                </span>
              </td>
              <td>{u.is_superadmin ? "✓" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
