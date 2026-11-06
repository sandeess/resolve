import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  ChevronRight,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { useState } from "react"

import {
  type TicketDetail,
  type TicketPriority,
  TicketsService,
} from "@/client"
import { PersonAvatar } from "@/components/Shell/PersonAvatar"
import { PriorityBadge, StatusBadge } from "@/components/Tickets/badges"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { useJournalAccess } from "@/lib/journal-context"
import { fullDate, timeAgo } from "@/lib/time"
import { handleError } from "@/utils"

export const Route = createFileRoute(
  "/_layout/journals/$journalId/tickets/$ticketId",
)({
  component: TicketPage,
  head: () => ({ meta: [{ title: "Ticket - Resolve" }] }),
})

const PRIORITIES: TicketPriority[] = ["low", "normal", "high"]
const textarea =
  "w-full rounded-lg border bg-card px-3.5 py-2.5 text-sm outline-none focus-visible:border-primary focus-visible:ring-[3px] focus-visible:ring-primary/25"

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className="text-sm">{children}</dd>
    </div>
  )
}

function TicketPage() {
  const { journalId, ticketId } = Route.useParams()
  const { journal, canWork, canApprove } = useJournalAccess()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [comment, setComment] = useState("")
  const [answer, setAnswer] = useState("")

  const { data: ticket } = useQuery({
    queryKey: ["ticket", ticketId],
    queryFn: async () =>
      (await TicketsService.readTicket({ path: { ticket_id: ticketId } })).data,
  })

  // Every action returns the updated ticket: cache it and refresh the lists.
  const refresh = (updated: TicketDetail, message?: string) => {
    queryClient.setQueryData(["ticket", ticketId], updated)
    void queryClient.invalidateQueries({ queryKey: ["tickets"] })
    if (message) showSuccessToast(message)
  }
  const onError = handleError.bind(showErrorToast)

  const addComment = useMutation({
    mutationFn: async () =>
      (
        await TicketsService.addMessage({
          path: { ticket_id: ticketId },
          body: { body: comment },
        })
      ).data,
    onSuccess: (updated) => {
      setComment("")
      refresh(updated)
    },
    onError,
  })
  const update = useMutation({
    mutationFn: async (body: {
      priority?: TicketPriority
      assign_to_me?: boolean
      unassign?: boolean
    }) =>
      (
        await TicketsService.updateTicket({
          path: { ticket_id: ticketId },
          body,
        })
      ).data,
    onSuccess: (updated) => refresh(updated),
    onError,
  })
  const resolve = useMutation({
    mutationFn: async (approve: boolean) =>
      (
        await TicketsService.resolveTicket({
          path: { ticket_id: ticketId },
          body: { answer, approve },
        })
      ).data,
    onSuccess: (updated) => {
      setAnswer("")
      refresh(
        updated,
        updated.status === "closed"
          ? "Approved: Ask can now cite this answer"
          : "Saved, waiting for approval",
      )
    },
    onError,
  })
  const approve = useMutation({
    mutationFn: async () =>
      (await TicketsService.approveTicket({ path: { ticket_id: ticketId } }))
        .data,
    onSuccess: (updated) =>
      refresh(updated, "Approved: Ask can now cite this answer"),
    onError,
  })
  const reopen = useMutation({
    mutationFn: async () =>
      (await TicketsService.reopenTicket({ path: { ticket_id: ticketId } }))
        .data,
    onSuccess: (updated) =>
      refresh(updated, "Reopened. The answer is no longer used by Ask"),
    onError,
  })

  if (!ticket) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-48 w-full rounded-3xl" />
      </div>
    )
  }

  const mine = ticket.assignee_email === user?.email
  const canComment = canWork || ticket.created_by_email === user?.email
  const draftReady = answer.trim().length >= 3

  return (
    <div className="flex flex-col gap-6">
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1 text-sm text-muted-foreground"
      >
        <Link
          to="/journals/$journalId/tickets"
          params={{ journalId }}
          className="rounded-md hover:text-foreground"
        >
          Tickets
        </Link>
        <ChevronRight className="size-4" />
        <span className="text-foreground">T-{ticket.number}</span>
      </nav>

      <header className="flex flex-col gap-3">
        <h1 className="text-2xl leading-tight sm:text-3xl">{ticket.title}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={ticket.status} />
          <PriorityBadge priority={ticket.priority} />
          {ticket.source === "ask_escalation" && (
            <Badge variant="outline">
              <Sparkles /> from Ask
            </Badge>
          )}
          <span
            className="flex items-center gap-2 text-sm text-muted-foreground"
            title={fullDate(ticket.created_at)}
          >
            <PersonAvatar
              email={ticket.created_by_email}
              className="size-6 text-[10px]"
            />
            {ticket.created_by_email.split("@")[0]} ·{" "}
            {timeAgo(ticket.created_at)}
          </span>
        </div>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="flex min-w-0 flex-col gap-6">
          {ticket.description && (
            <p className="rounded-2xl bg-muted/60 px-5 py-4 whitespace-pre-wrap">
              {ticket.description}
            </p>
          )}

          {ticket.resolution && (
            <section className="flex flex-col gap-4 rounded-3xl bg-secondary/40 p-6">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg">Answer</h2>
                {ticket.status === "closed" ? (
                  <Badge className="bg-success-soft text-success">
                    <ShieldCheck /> searchable in Ask
                  </Badge>
                ) : (
                  <Badge variant="outline">not searchable until approved</Badge>
                )}
              </div>
              <p className="text-base leading-7 whitespace-pre-wrap">
                {ticket.resolution.answer}
              </p>
              <p className="text-xs text-muted-foreground">
                Written by {ticket.resolution.resolved_by_email}
                {ticket.resolution.approved_by_email &&
                  ` · approved by ${ticket.resolution.approved_by_email}`}
              </p>
              <div className="flex flex-wrap gap-2">
                {ticket.status === "resolved" && canApprove && (
                  <LoadingButton
                    loading={approve.isPending}
                    onClick={() => approve.mutate()}
                  >
                    <ShieldCheck /> Approve and publish to Ask
                  </LoadingButton>
                )}
                {canWork && (
                  <Button
                    variant="outline"
                    disabled={reopen.isPending}
                    onClick={() => reopen.mutate()}
                  >
                    <RotateCcw /> Reopen
                  </Button>
                )}
              </div>
            </section>
          )}

          {canWork && ticket.status !== "closed" && (
            <section className="flex flex-col gap-3 rounded-3xl border p-6">
              <h2 className="text-lg">
                {ticket.resolution ? "Edit the answer" : "Write the answer"}
              </h2>
              <textarea
                className={`${textarea} min-h-28`}
                placeholder="A reusable answer. Once approved, Ask can cite it for the next person who asks."
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                aria-label="Answer"
              />
              <div className="flex flex-wrap gap-2">
                <LoadingButton
                  variant={canApprove ? "outline" : "default"}
                  loading={resolve.isPending && resolve.variables === false}
                  disabled={!draftReady || resolve.isPending}
                  onClick={() => resolve.mutate(false)}
                >
                  Save for approval
                </LoadingButton>
                {canApprove && (
                  <LoadingButton
                    loading={resolve.isPending && resolve.variables === true}
                    disabled={!draftReady || resolve.isPending}
                    onClick={() => resolve.mutate(true)}
                  >
                    <ShieldCheck /> Save and approve
                  </LoadingButton>
                )}
              </div>
            </section>
          )}

          <section
            aria-labelledby="conversation"
            className="flex flex-col gap-4"
          >
            <h2 id="conversation" className="text-lg">
              Conversation
            </h2>
            {ticket.messages.length === 0 && (
              <p className="text-sm text-muted-foreground">No messages yet.</p>
            )}
            <ol className="flex flex-col gap-4">
              {ticket.messages.map((message) => (
                <li key={message.id} className="flex gap-3">
                  <PersonAvatar email={message.author_email} />
                  <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md border px-4 py-3">
                    <p className="mb-1 flex flex-wrap items-baseline gap-2 text-sm">
                      <span className="font-medium">
                        {message.author_email.split("@")[0]}
                      </span>
                      <span
                        className="text-xs text-muted-foreground"
                        title={fullDate(message.created_at)}
                      >
                        {timeAgo(message.created_at)}
                      </span>
                    </p>
                    <p className="text-sm leading-6 whitespace-pre-wrap">
                      {message.body}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
            {canComment && (
              <form
                className="flex items-end gap-2"
                onSubmit={(event) => {
                  event.preventDefault()
                  if (comment.trim()) addComment.mutate()
                }}
              >
                <textarea
                  className={`${textarea} min-h-12 flex-1 resize-none`}
                  rows={2}
                  placeholder="Reply..."
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      (event.metaKey || event.ctrlKey) &&
                      comment.trim()
                    ) {
                      event.preventDefault()
                      addComment.mutate()
                    }
                  }}
                  aria-label="Reply"
                />
                <LoadingButton
                  type="submit"
                  size="icon"
                  loading={addComment.isPending}
                  disabled={!comment.trim()}
                  aria-label="Send reply"
                >
                  <Send />
                </LoadingButton>
              </form>
            )}
          </section>
        </div>

        <aside className="rounded-2xl border p-5 lg:sticky lg:top-24">
          <h2 className="sr-only">Details</h2>
          <dl className="flex flex-col gap-5">
            <Field label="Journal">{journal.name}</Field>
            <Field label="Assignee">
              <div className="flex items-center gap-2">
                {ticket.assignee_email ? (
                  <>
                    <PersonAvatar
                      email={ticket.assignee_email}
                      className="size-6 text-[10px]"
                    />
                    <span className="truncate">
                      {ticket.assignee_email.split("@")[0]}
                    </span>
                  </>
                ) : (
                  <span className="text-muted-foreground">Unassigned</span>
                )}
              </div>
              {canWork && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-3 mt-1"
                  onClick={() =>
                    update.mutate(
                      mine ? { unassign: true } : { assign_to_me: true },
                    )
                  }
                >
                  {mine ? "Unassign me" : "Assign to me"}
                </Button>
              )}
            </Field>
            <Field label="Priority">
              {canWork ? (
                <select
                  aria-label="Priority"
                  className="h-9 w-full rounded-lg border bg-card px-3 text-sm capitalize"
                  value={ticket.priority}
                  onChange={(event) =>
                    update.mutate({
                      priority: event.target.value as TicketPriority,
                    })
                  }
                >
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="capitalize">{ticket.priority}</span>
              )}
            </Field>
            <Field label="Raised">{fullDate(ticket.created_at)}</Field>
            <Field label="Last update">{timeAgo(ticket.updated_at)}</Field>
          </dl>
        </aside>
      </div>
    </div>
  )
}
