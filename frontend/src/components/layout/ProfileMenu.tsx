import { NavLink, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import { Avatar } from "@/components/ui/Avatar";
import type { ImageRef } from "@/types";

/** Desktop navbar avatar — click opens a dropdown with the profile sub-pages
 * and logout, so the navbar itself only shows the round picture. */
export function ProfileMenu({
  profileImage,
  firstName,
  lastName,
  email,
}: {
  profileImage?: ImageRef | null;
  firstName?: string | null;
  lastName?: string | null;
  email?: string | null;
}) {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const onLogout = async () => {
    setOpen(false);
    await logout();
    navigate("/login");
  };

  return (
    <div className="sf-options" ref={ref} title={email ?? undefined}>
      <button
        type="button"
        className="sf-navbar__avatarbtn"
        aria-label={t("nav.profilo")}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Avatar size="sm" profileImage={profileImage} firstName={firstName} lastName={lastName} />
      </button>
      {open && (
        <div className="sf-options__panel sf-optionsmenu__panel" role="menu">
          <NavLink
            to="/profilo/anagrafica"
            className="sf-optionsmenu__item"
            role="menuitem"
            onClick={() => setOpen(false)}
          >
            {t("profile.myProfile")}
          </NavLink>
          <NavLink
            to="/profilo/password"
            className="sf-optionsmenu__item"
            role="menuitem"
            onClick={() => setOpen(false)}
          >
            {t("profile.changePassword")}
          </NavLink>
          <NavLink
            to="/profilo/barche"
            className="sf-optionsmenu__item"
            role="menuitem"
            onClick={() => setOpen(false)}
          >
            {t("profile.boats")}
          </NavLink>
          <NavLink
            to="/profilo/devices"
            className="sf-optionsmenu__item"
            role="menuitem"
            onClick={() => setOpen(false)}
          >
            {t("profile.devices")}
          </NavLink>
          <button
            type="button"
            role="menuitem"
            className="sf-optionsmenu__item sf-optionsmenu__item--danger"
            onClick={onLogout}
          >
            {t("auth.logout")}
          </button>
        </div>
      )}
    </div>
  );
}
