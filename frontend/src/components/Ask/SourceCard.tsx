import { Link } from "@tanstack/react-router"
import { FileText, LifeBuoy } from "lucide-react"
import { useState } from "react"

import type { Citation } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const CLAMP_AT = 160

/** One source behind an answer: where it came from, and the exact words. */
export function SourceCard({
  citation,
  journalId,
  highlighted,
}: {
  citation: Citation
  journalId: string
  highlighted?: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const isTicket = citation.source_type === "ticket"
  const Icon = isTicket ? LifeBuoy : FileText
  const long = citation.snippet.length > CLAMP_AT

  return (
    <article
      id={`source-${citation.n}`}
      className={cn(
        "flex flex-col gap-3 rounded-2xl border bg-card p-4 transition-[box-shadow,border-color,background-color] duration-300 hover:shadow-e1",
        highlighted && "border-primary bg-secondary/50 shadow-e1",
      )}
    >
      <header className="flex items-center gap-3">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground">
          {citation.n}
        </span>
        <Icon className="size-4 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium">
          {isTicket ? `Ticket ${citation.source_name}` : citation.source_name}
        </span>
        {isTicket ? (
          <Badge variant="secondary">approved answer</Badge>
        ) : (
          <Badge variant="outline">v{citation.version_no}</Badge>
        )}
      </header>
      {!isTicket && citation.locator && (
        <p className="-mt-1 truncate pl-9 text-xs text-muted-foreground">
          {citation.locator}
        </p>
      )}
      <blockquote
        className={cn(
          "border-l-2 pl-3 text-sm leading-relaxed text-muted-foreground",
          !expanded && "line-clamp-3",
        )}
      >
        {citation.snippet}
      </blockquote>
      <div className="flex items-center gap-4 text-sm">
        {long && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="font-medium text-primary hover:underline"
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
        {isTicket && citation.ticket_id && (
          <Link
            to="/journals/$journalId/tickets/$ticketId"
            params={{ journalId, ticketId: citation.ticket_id }}
            className="ml-auto font-medium text-primary hover:underline"
          >
            Open ticket
          </Link>
        )}
      </div>
    </article>
  )
}
