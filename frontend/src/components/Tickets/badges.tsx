import type { TicketPriority, TicketStatus } from "@/client"
import { cn } from "@/lib/utils"

const STATUS: Record<TicketStatus, { label: string; className: string }> = {
  open: { label: "Open", className: "bg-warning-soft text-warning" },
  resolved: {
    label: "Awaiting approval",
    className: "bg-secondary text-secondary-foreground",
  },
  closed: { label: "Closed", className: "bg-success-soft text-success" },
}

export function StatusBadge({
  status,
  className,
}: {
  status: TicketStatus
  className?: string
}) {
  const { label, className: tone } = STATUS[status]
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full px-2.5 text-xs font-medium whitespace-nowrap",
        tone,
        className,
      )}
    >
      {label}
    </span>
  )
}

/** Only unusual priorities are shown; "normal" is the quiet default. */
export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  if (priority === "normal") return null
  const high = priority === "high"
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium",
        high
          ? "border-destructive/30 text-destructive"
          : "text-muted-foreground",
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          high ? "bg-destructive" : "bg-muted-foreground",
        )}
      />
      {high ? "High" : "Low"}
    </span>
  )
}
