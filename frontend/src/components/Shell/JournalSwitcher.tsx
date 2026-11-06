import { useNavigate, useParams } from "@tanstack/react-router"
import { Check, ChevronsUpDown } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { useJournals } from "@/lib/journals"

/** Picks which journal you are working in; everything below follows it. */
export function JournalSwitcher({ onNavigate }: { onNavigate?: () => void }) {
  const { journalId } = useParams({ strict: false }) as { journalId?: string }
  const navigate = useNavigate()
  const { data, isLoading } = useJournals()
  const current = data?.data.find((j) => j.id === journalId)

  if (isLoading) return <Skeleton className="mb-3 h-14 rounded-2xl" />
  if (!data || data.count === 0) return null

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="mb-3 flex h-14 w-full items-center gap-3 rounded-2xl border bg-card px-4 text-left transition-shadow hover:shadow-e1 focus-visible:shadow-e1"
          aria-label="Switch journal"
        >
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-xs font-semibold text-secondary-foreground">
            {(current?.code ?? "?").slice(0, 3)}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">
              {current?.name ?? "Choose a journal"}
            </span>
            <span className="block truncate text-xs text-muted-foreground">
              {current ? (current.role ?? "administrator") : "Switch journal"}
            </span>
          </span>
          <ChevronsUpDown className="size-4 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72 rounded-2xl p-2">
        <DropdownMenuLabel className="px-3 py-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Journals
        </DropdownMenuLabel>
        {data.data.map((journal) => (
          <DropdownMenuItem
            key={journal.id}
            className="gap-3 rounded-xl py-2.5"
            onClick={() => {
              onNavigate?.()
              void navigate({
                to: "/journals/$journalId/ask",
                params: { journalId: journal.id },
              })
            }}
          >
            <span className="flex size-8 items-center justify-center rounded-lg bg-secondary text-xs font-semibold text-secondary-foreground">
              {journal.code.slice(0, 3)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm">{journal.name}</span>
            </span>
            {journal.role && <Badge variant="outline">{journal.role}</Badge>}
            {journal.id === journalId && <Check className="text-primary" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
