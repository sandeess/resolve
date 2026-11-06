import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowUpRight, BookOpen, Inbox } from "lucide-react"
import { useMemo, useState } from "react"

import { SearchBox } from "@/components/Ask/SearchBox"
import CreateJournal from "@/components/Journals/CreateJournal"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { useNarrow } from "@/hooks/useNarrow"
import { lastJournal, useJournals } from "@/lib/journals"

export const Route = createFileRoute("/_layout/")({
  component: Home,
  head: () => ({ meta: [{ title: "Resolve" }] }),
})

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 5) return "Working late"
  if (hour < 12) return "Good morning"
  if (hour < 18) return "Good afternoon"
  return "Good evening"
}

function Home() {
  const { user } = useAuth()
  const narrow = useNarrow()
  const navigate = useNavigate()
  const { data, isLoading } = useJournals()
  const [question, setQuestion] = useState("")
  const [chosen, setChosen] = useState<string>("")

  const journals = data?.data ?? []
  // Ask goes to the journal picked here, else the last one used, else the first.
  const targetId = useMemo(
    () =>
      journals.find((j) => j.id === chosen)?.id ??
      journals.find((j) => j.id === lastJournal.get())?.id ??
      journals[0]?.id,
    [journals, chosen],
  )
  const first = (user?.full_name ?? user?.email ?? "").split(/[ @]/)[0]

  const ask = () => {
    if (!targetId) return
    void navigate({
      to: "/journals/$journalId/ask",
      params: { journalId: targetId },
      search: { q: question.trim() },
    })
  }

  return (
    <div className="flex flex-col gap-12 py-4 sm:py-10">
      <section className="flex flex-col items-center gap-7 text-center">
        <div className="space-y-2">
          <p className="text-muted-foreground">
            {greeting()}
            {first ? `, ${first}` : ""}
          </p>
          <h1 className="text-3xl sm:text-5xl">What would you like to know?</h1>
        </div>
        <div className="w-full max-w-2xl">
          <SearchBox
            value={question}
            onChange={setQuestion}
            onSubmit={ask}
            placeholder={
              journals.length === 0
                ? "Join a journal to start asking"
                : narrow
                  ? "Ask a question"
                  : "Ask about a style rule, an author query, a manuscript..."
            }
            scope={
              journals.length > 1
                ? {
                    value: targetId ?? "",
                    onChange: setChosen,
                    options: journals.map((j) => ({
                      id: j.id,
                      label: `In ${j.name}`,
                    })),
                  }
                : undefined
            }
            autoFocus
          />
        </div>
        <p className="hidden text-sm text-muted-foreground sm:block">
          Press <kbd className="rounded-md border px-1.5 py-0.5 text-xs">/</kbd>{" "}
          to search from anywhere
        </p>
      </section>

      <section
        aria-labelledby="journals-heading"
        className="flex flex-col gap-4"
      >
        <div className="flex items-center justify-between px-1">
          <h2 id="journals-heading" className="text-lg">
            Your journals
          </h2>
          {user?.is_admin && <CreateJournal />}
        </div>

        {isLoading && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-28 rounded-2xl" />
            ))}
          </div>
        )}

        {!isLoading && journals.length === 0 && (
          <div className="flex flex-col items-center gap-3 rounded-3xl bg-muted/60 px-6 py-12 text-center">
            <span className="flex size-14 items-center justify-center rounded-full bg-card text-muted-foreground shadow-e1">
              <Inbox className="size-7" />
            </span>
            <h3 className="text-lg">No journals yet</h3>
            <p className="max-w-sm text-muted-foreground">
              You haven't been added to a journal. Ask an administrator to add
              you, then it will appear here.
            </p>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {journals.map((journal) => (
            <Link
              key={journal.id}
              to="/journals/$journalId/ask"
              params={{ journalId: journal.id }}
              className="group flex flex-col gap-4 rounded-2xl border bg-card p-5 transition-shadow hover:shadow-e2"
            >
              <div className="flex items-start justify-between">
                <span className="flex size-11 items-center justify-center rounded-xl bg-secondary text-sm font-semibold text-secondary-foreground">
                  {journal.code.slice(0, 3)}
                </span>
                <ArrowUpRight className="size-5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
              </div>
              <div className="space-y-1.5">
                <h3 className="flex items-start gap-2 font-medium">
                  <BookOpen className="mt-1 size-4 shrink-0 text-muted-foreground" />
                  <span className="line-clamp-2">{journal.name}</span>
                </h3>
                {journal.role ? (
                  <Badge variant="outline">{journal.role}</Badge>
                ) : (
                  <Badge variant="secondary">administrator</Badge>
                )}
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
