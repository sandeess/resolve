import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate } from "@tanstack/react-router"
import { Inbox, LifeBuoy, Plus, UserRound } from "lucide-react"
import { useMemo, useState } from "react"

import { type TicketStatus, TicketsService } from "@/client"
import { PersonAvatar } from "@/components/Shell/PersonAvatar"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { useTickets } from "@/lib/tickets"
import { fullDate, timeAgo } from "@/lib/time"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { PriorityBadge, StatusBadge } from "./badges"

type Filter = "all" | TicketStatus
const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "resolved", label: "Awaiting approval" },
  { value: "closed", label: "Closed" },
]

const EMPTY: Record<Filter, { title: string; hint: string }> = {
  all: {
    title: "No tickets yet",
    hint: "Questions the documents can't answer end up here.",
  },
  open: {
    title: "Nothing open",
    hint: "Everything raised has an answer. Nice.",
  },
  resolved: {
    title: "Nothing waiting for approval",
    hint: "Answers written by the team appear here for a lead to approve.",
  },
  closed: {
    title: "No closed tickets",
    hint: "Approved answers become searchable knowledge.",
  },
}

function NewTicketDialog({
  journalId,
  open,
  onOpenChange,
}: {
  journalId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { showErrorToast } = useCustomToast()
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")

  const create = useMutation({
    mutationFn: async () =>
      (
        await TicketsService.createTicket({
          path: { journal_id: journalId },
          body: { title, description },
        })
      ).data,
    onSuccess: (ticket) => {
      setTitle("")
      setDescription("")
      onOpenChange(false)
      void queryClient.invalidateQueries({ queryKey: ["tickets", journalId] })
      void navigate({
        to: "/journals/$journalId/tickets/$ticketId",
        params: { journalId, ticketId: ticket.id },
      })
    },
    onError: handleError.bind(showErrorToast),
  })
  const valid = title.trim().length >= 3

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          className="grid gap-5"
          onSubmit={(event) => {
            event.preventDefault()
            if (valid) create.mutate()
          }}
        >
          <DialogHeader>
            <DialogTitle className="text-xl">New ticket</DialogTitle>
            <DialogDescription>
              Describe what you need an answer to. The team will reply here.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="ticket-title">Question</Label>
            <Input
              id="ticket-title"
              autoFocus
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. Can supplementary data be uploaded as a zip?"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ticket-details">Details (optional)</Label>
            <textarea
              id="ticket-details"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={4}
              className="min-h-28 rounded-lg border bg-card px-3.5 py-2.5 text-sm outline-none focus-visible:border-primary focus-visible:ring-[3px] focus-visible:ring-primary/25"
              placeholder="Anything that helps: manuscript id, what you've tried..."
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <LoadingButton
              type="submit"
              loading={create.isPending}
              disabled={!valid}
            >
              Raise ticket
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/** The journal's ticket inbox: filter by state, open one to work on it. */
export default function TicketsPanel({ journalId }: { journalId: string }) {
  const { data, isLoading } = useTickets(journalId)
  const [filter, setFilter] = useState<Filter>("all")
  const [creating, setCreating] = useState(false)

  const tickets = data?.data ?? []
  const counts = useMemo(
    () => ({
      all: tickets.length,
      open: tickets.filter((t) => t.status === "open").length,
      resolved: tickets.filter((t) => t.status === "resolved").length,
      closed: tickets.filter((t) => t.status === "closed").length,
    }),
    [tickets],
  )
  const shown =
    filter === "all" ? tickets : tickets.filter((t) => t.status === filter)

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl">Tickets</h1>
          <p className="text-muted-foreground">
            Questions for the team. Approved answers become searchable.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus /> New ticket
        </Button>
      </header>

      <div
        role="tablist"
        aria-label="Filter tickets"
        className="flex flex-wrap gap-2"
      >
        {FILTERS.map(({ value, label }) => {
          const active = filter === value
          return (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setFilter(value)}
              className={cn(
                "flex h-9 items-center gap-2 rounded-full border px-4 text-sm transition-colors",
                active
                  ? "border-transparent bg-secondary font-medium text-secondary-foreground"
                  : "hover:bg-accent",
              )}
            >
              {label}
              <span
                className={cn(
                  "text-xs",
                  active
                    ? "text-secondary-foreground/80"
                    : "text-muted-foreground",
                )}
              >
                {counts[value]}
              </span>
            </button>
          )
        })}
      </div>

      <div className="overflow-hidden rounded-2xl border">
        {isLoading &&
          [0, 1, 2].map((i) => (
            <div
              key={i}
              className="flex items-center gap-4 border-b px-4 py-4 last:border-0"
            >
              <Skeleton className="size-8 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            </div>
          ))}

        {!isLoading && shown.length === 0 && (
          <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
            <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <Inbox className="size-7" />
            </span>
            <h2 className="text-lg">{EMPTY[filter].title}</h2>
            <p className="max-w-sm text-sm text-muted-foreground">
              {EMPTY[filter].hint}
            </p>
            {filter === "all" && (
              <Button variant="outline" onClick={() => setCreating(true)}>
                <LifeBuoy /> Raise the first ticket
              </Button>
            )}
          </div>
        )}

        {shown.map((ticket) => (
          <Link
            key={ticket.id}
            to="/journals/$journalId/tickets/$ticketId"
            params={{ journalId, ticketId: ticket.id }}
            className="flex items-center gap-4 border-b px-4 py-3.5 transition-colors last:border-0 hover:bg-accent/70 focus-visible:bg-accent"
          >
            <PersonAvatar email={ticket.created_by_email} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{ticket.title}</p>
              <p
                className="truncate text-sm text-muted-foreground"
                title={fullDate(ticket.created_at)}
              >
                T-{ticket.number} · {ticket.created_by_email.split("@")[0]} ·{" "}
                {timeAgo(ticket.created_at)}
              </p>
            </div>
            <div className="hidden items-center gap-2 sm:flex">
              <PriorityBadge priority={ticket.priority} />
              <StatusBadge status={ticket.status} />
            </div>
            <div
              className="flex items-center"
              title={ticket.assignee_email ?? "Unassigned"}
            >
              {ticket.assignee_email ? (
                <PersonAvatar email={ticket.assignee_email} />
              ) : (
                <span className="flex size-8 items-center justify-center rounded-full border border-dashed text-muted-foreground">
                  <UserRound className="size-4" />
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>

      <NewTicketDialog
        journalId={journalId}
        open={creating}
        onOpenChange={setCreating}
      />
    </div>
  )
}
