import { useMutation, useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Clock, History, Sparkles, TriangleAlert } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { AskService, JournalsService, TicketsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { useAskHistory } from "@/lib/ask-history"
import { useJournalAccess } from "@/lib/journal-context"
import { handleError } from "@/utils"
import { AnswerCard } from "./AnswerCard"
import { SearchBox } from "./SearchBox"
import { SourceCard } from "./SourceCard"

const SUGGESTIONS = [
  "How should references be formatted?",
  "What file format do figures need?",
  "Is a cover letter required?",
  "How long may the abstract be?",
]
const PREFETCH_DELAY_MS = 600
const PREFETCH_MIN_CHARS = 8

function Thinking({ journalName }: { journalName: string }) {
  return (
    <div
      className="flex flex-col gap-4 rounded-3xl bg-secondary/40 p-6 sm:p-8"
      aria-busy="true"
    >
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Sparkles className="size-4 animate-pulse text-primary" />
        Reading {journalName}'s documents...
      </p>
      <Skeleton className="h-5 w-11/12" />
      <Skeleton className="h-5 w-9/12" />
      <Skeleton className="h-5 w-7/12" />
    </div>
  )
}

/** Search-first Ask: a hero box until you ask, then the answer with its sources. */
export function AskPage({
  journalId,
  question,
  articleId,
}: {
  journalId: string
  question?: string
  articleId?: string
}) {
  const { journal } = useJournalAccess()
  const navigate = useNavigate()
  const { showErrorToast } = useCustomToast()
  const history = useAskHistory(journalId)
  const searchRef = useRef<HTMLInputElement>(null)
  const [input, setInput] = useState(question ?? "")
  const [scope, setScope] = useState(articleId ?? "")
  const [highlighted, setHighlighted] = useState<number | null>(null)

  // Keep the box in step with back/forward navigation.
  useEffect(() => {
    setInput(question ?? "")
    setScope(articleId ?? "")
  }, [question, articleId])

  const { data: articles } = useQuery({
    queryKey: ["articles", journalId],
    queryFn: async () =>
      (await JournalsService.listArticles({ path: { journal_id: journalId } }))
        .data,
  })
  const scopeOptions = [
    { id: "", label: "Whole journal" },
    ...(articles ?? []).map((a) => ({
      id: a.id,
      label: `${a.manuscript_id} - ${a.title}`,
    })),
  ]

  const answer = useQuery({
    queryKey: ["ask", journalId, articleId ?? "", question],
    enabled: Boolean(question),
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () =>
      (
        await AskService.askJournal({
          path: { journal_id: journalId },
          body: { question: question as string, article_id: articleId || null },
        })
      ).data,
  })

  useEffect(() => {
    if (answer.isSuccess && question) history.remember(question)
  }, [answer.isSuccess, question, history.remember])

  // Embed the question while the user is still typing, so Enter only waits for the model.
  useEffect(() => {
    const text = input.trim()
    if (text.length < PREFETCH_MIN_CHARS || text === question) return
    const timer = setTimeout(() => {
      void AskService.prefetchQuestion({
        path: { journal_id: journalId },
        body: { question: text, article_id: scope || null },
      }).catch(() => undefined)
    }, PREFETCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [input, scope, journalId, question])

  const ask = (text: string, article = scope) => {
    const q = text.trim()
    if (q.length < 3) return
    void navigate({
      to: "/journals/$journalId/ask",
      params: { journalId },
      search: { q, a: article || undefined },
    })
  }

  const raiseTicket = useMutation({
    mutationFn: async () => {
      // The ticket text becomes searchable knowledge once approved, so keep the
      // "why" out of it and record it as a message instead.
      const ticket = (
        await TicketsService.createTicket({
          path: { journal_id: journalId },
          body: {
            title: (question ?? "").slice(0, 300),
            article_id: articleId || null,
            source: "ask_escalation",
          },
        })
      ).data
      await TicketsService.addMessage({
        path: { ticket_id: ticket.id },
        body: { body: "Ask could not answer this from the current documents." },
      })
      return ticket
    },
    onSuccess: (ticket) =>
      navigate({
        to: "/journals/$journalId/tickets/$ticketId",
        params: { journalId, ticketId: ticket.id },
      }),
    onError: handleError.bind(showErrorToast),
  })

  const cite = (n: number) => {
    setHighlighted(n)
    document
      .getElementById(`source-${n}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" })
    setTimeout(
      () => setHighlighted((current) => (current === n ? null : current)),
      1800,
    )
  }

  const box = (size: "hero" | "compact") => (
    <SearchBox
      ref={searchRef}
      size={size}
      value={input}
      onChange={setInput}
      onSubmit={() => ask(input)}
      busy={answer.isFetching}
      placeholder={`Ask about ${journal.name}`}
      scope={{ value: scope, options: scopeOptions, onChange: setScope }}
      autoFocus={!question}
    />
  )

  // ---- Before the first question: the hero ---------------------------------
  if (!question) {
    return (
      <div className="flex min-h-[58svh] flex-col items-center justify-center gap-8 py-8 text-center">
        <div className="space-y-3">
          <h1 className="text-3xl sm:text-4xl">What would you like to know?</h1>
          <p className="text-muted-foreground">
            Answers come from {journal.name}'s latest files and approved ticket
            answers, with sources.
          </p>
        </div>
        <div className="w-full max-w-2xl">{box("hero")}</div>
        <div className="flex max-w-2xl flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => ask(s)}
              className="flex h-9 items-center gap-2 rounded-full border bg-card px-4 text-sm transition-colors hover:bg-accent"
            >
              <Sparkles className="size-3.5 text-primary" />
              {s}
            </button>
          ))}
        </div>
        {history.items.length > 0 && (
          <div className="flex w-full max-w-2xl flex-col items-start gap-1 text-left">
            <div className="mb-1 flex w-full items-center justify-between px-3">
              <p className="flex items-center gap-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                <History className="size-3.5" /> Recent
              </p>
              <button
                type="button"
                onClick={history.forget}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Clear
              </button>
            </div>
            {history.items.slice(0, 4).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => ask(item)}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition-colors hover:bg-accent"
              >
                <Clock className="size-4 shrink-0 text-muted-foreground" />
                <span className="truncate">{item}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  // ---- After asking: compact box, answer, sources --------------------------
  const result = answer.data
  return (
    <div className="flex flex-col gap-6">
      <div className="sticky top-16 z-10 -mx-1 bg-card/90 px-1 py-2 backdrop-blur">
        {box("compact")}
      </div>

      {answer.isFetching && <Thinking journalName={journal.name} />}

      {answer.isError && !answer.isFetching && (
        <div className="flex flex-col items-center gap-4 rounded-3xl bg-destructive/5 px-6 py-10 text-center">
          <TriangleAlert className="size-8 text-destructive" />
          <div className="space-y-1">
            <h2 className="text-xl">The answering service didn't respond</h2>
            <p className="text-muted-foreground">
              Your question wasn't lost. Try again in a moment.
            </p>
          </div>
          <Button onClick={() => void answer.refetch()}>Try again</Button>
        </div>
      )}

      {result && !answer.isFetching && (
        <div className="animate-in fade-in-0 slide-in-from-bottom-2 flex flex-col gap-8 duration-300">
          <AnswerCard
            result={result}
            onCite={cite}
            raising={raiseTicket.isPending}
            onRaiseTicket={() => raiseTicket.mutate()}
            onRephrase={() => searchRef.current?.focus()}
          />
          {result.citations && result.citations.length > 0 && (
            <section
              aria-labelledby="sources-heading"
              className="flex flex-col gap-3"
            >
              <h2
                id="sources-heading"
                className="px-1 text-sm font-medium text-muted-foreground"
              >
                Sources ({result.citations.length})
              </h2>
              <div className="grid gap-3 md:grid-cols-2">
                {result.citations.map((c) => (
                  <SourceCard
                    key={c.chunk_id}
                    citation={c}
                    journalId={journalId}
                    highlighted={highlighted === c.n}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
