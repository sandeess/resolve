import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

/** The mark: a speech bubble with a tick, i.e. "a question, resolved". */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      aria-hidden="true"
      className={cn("size-8 shrink-0", className)}
    >
      <rect width="32" height="32" rx="9" fill="#d9b26a" />
      <path
        d="M9 10.5A2.5 2.5 0 0 1 11.5 8h9A2.5 2.5 0 0 1 23 10.5v6a2.5 2.5 0 0 1-2.5 2.5H15l-3.6 3.2c-.5.4-1.4.1-1.4-.6V19h-.5A.5.5 0 0 1 9 18.5v-8Z"
        fill="#14100a"
      />
      <path
        d="m12.6 13.9 2.2 2.2 4.1-4.2"
        fill="none"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        stroke="#d9b26a"
      />
    </svg>
  )
}

export function Logo({
  className,
  asLink = true,
}: {
  className?: string
  asLink?: boolean
}) {
  const content = (
    <span className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="text-[1.375rem] font-medium tracking-tight text-foreground">
        Resolve
      </span>
    </span>
  )
  return asLink ? (
    <Link to="/" aria-label="Resolve home" className="rounded-lg">
      {content}
    </Link>
  ) : (
    content
  )
}
