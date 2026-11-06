import { Link, useParams } from "@tanstack/react-router"
import {
  BookOpen,
  FileText,
  Home,
  LifeBuoy,
  type LucideIcon,
  Sparkles,
  Users,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import useAuth from "@/hooks/useAuth"
import { useOpenTicketCount } from "@/lib/journals"
import { cn } from "@/lib/utils"
import { JournalSwitcher } from "./JournalSwitcher"

interface Item {
  label: string
  icon: LucideIcon
  to: string
  params?: Record<string, string>
  badge?: number
}

const itemClass =
  "group flex h-12 items-center gap-4 rounded-full px-5 text-sm font-medium text-foreground/80 transition-colors hover:bg-accent focus-visible:bg-accent"
const activeClass = "bg-secondary text-secondary-foreground hover:bg-secondary"

/** Left navigation. Sections belong to the journal you are in, like folders in Drive. */
export function NavRail({ onNavigate }: { onNavigate?: () => void }) {
  const { journalId } = useParams({ strict: false }) as { journalId?: string }
  const open = useOpenTicketCount(journalId)
  const { user } = useAuth()

  const items: Item[] = journalId
    ? [
        {
          label: "Ask",
          icon: Sparkles,
          to: "/journals/$journalId/ask",
          params: { journalId },
        },
        {
          label: "Tickets",
          icon: LifeBuoy,
          to: "/journals/$journalId/tickets",
          params: { journalId },
          badge: open.data,
        },
        {
          label: "Documents",
          icon: FileText,
          to: "/journals/$journalId/documents",
          params: { journalId },
        },
        {
          label: "Articles",
          icon: BookOpen,
          to: "/journals/$journalId/articles",
          params: { journalId },
        },
        ...(user?.is_admin
          ? [
              {
                label: "People",
                icon: Users,
                to: "/journals/$journalId/members",
                params: { journalId },
              },
            ]
          : []),
      ]
    : []

  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      <JournalSwitcher onNavigate={onNavigate} />
      <Link
        to="/"
        onClick={onNavigate}
        className={itemClass}
        activeOptions={{ exact: true }}
        activeProps={{ className: activeClass, "aria-current": "page" }}
      >
        <Home className="size-5" />
        Home
      </Link>
      {items.length > 0 && (
        <p className="px-5 pt-5 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          This journal
        </p>
      )}
      {items.map(({ label, icon: Icon, to, params, badge }) => (
        <Link
          key={label}
          to={to}
          params={params}
          onClick={onNavigate}
          className={itemClass}
          activeProps={{ className: activeClass, "aria-current": "page" }}
        >
          <Icon className="size-5" />
          <span className="flex-1">{label}</span>
          {badge ? (
            <Badge
              variant="secondary"
              className={cn(
                "min-w-6 justify-center bg-primary/10 text-primary",
              )}
              aria-label={`${badge} open`}
            >
              {badge}
            </Badge>
          ) : null}
        </Link>
      ))}
    </nav>
  )
}
