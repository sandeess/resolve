import { avatarColour, initials } from "@/lib/avatar"
import { cn } from "@/lib/utils"

/** A round initials avatar whose colour is stable per person. */
export function PersonAvatar({
  name,
  email,
  className,
}: {
  name?: string | null
  email: string
  className?: string
}) {
  return (
    <span
      aria-hidden="true"
      title={name ? `${name} (${email})` : email}
      style={{ backgroundColor: avatarColour(email) }}
      className={cn(
        "inline-flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white select-none",
        className,
      )}
    >
      {initials(email)}
    </span>
  )
}
