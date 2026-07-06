import type { ImageRef } from "@/types";

function initials(firstName?: string | null, lastName?: string | null): string {
  const a = firstName?.trim()?.[0] ?? "";
  const b = lastName?.trim()?.[0] ?? "";
  return (a + b).toUpperCase();
}

/** Round profile picture, falling back to first/last name initials when no
 * image is set. Used in the navbar and profile pages alike. */
export function Avatar({
  profileImage,
  firstName,
  lastName,
  size = "md",
  className = "",
}: {
  profileImage?: ImageRef | null;
  firstName?: string | null;
  lastName?: string | null;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizeClass = size === "sm" ? "sf-avatar--sm" : size === "lg" ? "sf-avatar--lg" : "";

  if (profileImage) {
    return (
      <img
        className={`sf-avatar ${sizeClass} ${className}`}
        src={profileImage.url}
        alt=""
      />
    );
  }

  const label = initials(firstName, lastName);
  return (
    <div className={`sf-avatar sf-avatar--initials ${sizeClass} ${className}`} aria-hidden={!label}>
      {label}
    </div>
  );
}
