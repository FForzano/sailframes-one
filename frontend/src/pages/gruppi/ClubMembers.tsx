import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, UserPlus } from "lucide-react";
import { clubsService, clubKeys } from "@/services/clubs";
import { rbacService } from "@/services/rbac";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { UserPicker } from "@/components/common/UserPicker";
import { userLabel } from "@/utils/format";
import { smartSearch } from "@/utils/smartSearch";
import { useClubContext } from "./ClubDetailLayout";
import type { ClubMember, UUID } from "@/types";

const roleKeys = { user: (userId: UUID) => ["user-roles", userId] as const };

/** Inline role editor for one member row. Roles are club-scoped grants on
 * top of membership (`user_roles.scope_club_id`), fetched per-user since
 * there's no bulk "list grants for this club" endpoint — acceptable since
 * club rosters are small (same reasoning as ClubDevices' per-row health
 * fetch). Only rendered for callers with `user_role.manage_scoped`. */
function MemberRoleCell({ clubId, userId }: { clubId: UUID; userId: UUID }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const queryClient = useQueryClient();

  const roles = useQuery({ queryKey: ["roles"], queryFn: rbacService.roles });
  const userRoles = useQuery({ queryKey: roleKeys.user(userId), queryFn: () => rbacService.userRoles(userId) });
  const current = userRoles.data?.find((r) => r.scope_club_id === clubId);
  // `UserRole.role` is never populated by the backend (user_roles only has
  // role_id, no joined name) — resolve the current role's name via the
  // catalog instead of trusting `current.role`.
  const currentRoleName = current ? roles.data?.find((r) => r.id === current.role_id)?.name : undefined;

  const change = useMutation({
    mutationFn: async (roleName: string) => {
      if (current) await rbacService.revoke(current.id);
      const role = roles.data?.find((r) => r.name === roleName);
      if (role) await rbacService.grant({ user_id: userId, role_id: role.id, scope_club_id: clubId });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: roleKeys.user(userId) }),
    onError: () => notify(t("errors.generic"), "error"),
  });

  return (
    <select
      className="sf-field__input sf-select sf-select--sm"
      aria-label={t("gruppi.roleGrants")}
      value={currentRoleName ?? ""}
      disabled={change.isPending || !roles.data}
      onChange={(e) => change.mutate(e.target.value)}
    >
      <option value="">{t("common.none")}</option>
      {(roles.data ?? [])
        .filter((r) => r.name !== "superadmin")
        .map((r) => (
          <option key={r.id} value={r.name}>
            {r.name}
          </option>
        ))}
    </select>
  );
}

export function ClubMembers() {
  const { clubId, isMember, managesMembers, managesRoles } = useClubContext();
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useToast();
  const [inviting, setInviting] = useState(false);
  const [query, setQuery] = useState("");

  const members = useQuery({
    queryKey: clubKeys.members(clubId),
    queryFn: () => clubsService.members(clubId),
    enabled: isMember,
  });

  const invalidateMembers = () => queryClient.invalidateQueries({ queryKey: clubKeys.members(clubId) });

  const approve = useMutation({
    mutationFn: (userId: UUID) => clubsService.setMemberStatus(clubId, userId, "active"),
    onSuccess: invalidateMembers,
  });
  const removeMember = useMutation({
    mutationFn: (userId: UUID) => clubsService.removeMember(clubId, userId),
    onSuccess: invalidateMembers,
  });
  const invite = useMutation({
    mutationFn: (userId: UUID) => clubsService.addMember(clubId, { user_id: userId }),
    onSuccess: async () => {
      setInviting(false);
      await invalidateMembers();
    },
    onError: () => notify(t("errors.generic"), "error"),
  });

  if (!isMember) return null;

  const active = members.data?.filter((m) => m.status !== "deleted") ?? [];
  const showSearch = active.length > 6;
  const visible: ClubMember[] = showSearch ? smartSearch(query, active, (m) => [userLabel(m.user)]) : active;

  return (
    <Card
      title={t("gruppi.clubMembers")}
      actions={
        managesMembers && (
          <Button
            variant="ghost"
            className="sf-btn--icon-sm"
            aria-label={t("gruppi.invite")}
            onClick={() => setInviting(true)}
          >
            <UserPlus size={16} />
          </Button>
        )
      }
    >
      {showSearch && (
        <div className="sf-entity-search" style={{ marginBottom: "0.75rem" }}>
          <Search size={16} className="sf-entity-search__icon" />
          <input
            className="sf-entity-search__input"
            type="search"
            placeholder={t("common.search")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      )}
      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th>{t("common.name")}</th>
              {managesRoles && <th>{t("gruppi.roleGrants")}</th>}
              {managesMembers && <th />}
            </tr>
          </thead>
          <tbody>
            {visible.map((m) => (
              <tr key={m.user_id}>
                <td>
                  {userLabel(m.user)}
                  {m.status !== "active" && (
                    <span className="sf-badge sf-badge--warning" style={{ marginLeft: "0.5rem" }}>
                      {m.status}
                    </span>
                  )}
                </td>
                {managesRoles && (
                  <td>
                    {m.status === "active" && <MemberRoleCell clubId={clubId} userId={m.user_id} />}
                  </td>
                )}
                {managesMembers && (
                  <td style={{ display: "flex", gap: "0.4rem" }}>
                    {(m.status === "requested" || m.status === "invited") && (
                      <Button className="sf-btn--sm" onClick={() => approve.mutate(m.user_id)}>
                        {t("gruppi.approve")}
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      className="sf-btn--sm"
                      onClick={() => removeMember.mutate(m.user_id)}
                    >
                      {m.user_id === user?.id ? t("gruppi.leave") : t("common.remove")}
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {inviting && (
        <Modal title={t("gruppi.invite")} onClose={() => setInviting(false)}>
          <UserPicker
            busy={invite.isPending}
            pickLabel={t("gruppi.invite")}
            onPick={(u) => invite.mutate(u.id)}
          />
        </Modal>
      )}
    </Card>
  );
}
