import { createFileRoute } from "@tanstack/react-router"

import { AskPage } from "@/components/Ask/AskPage"

interface AskSearch {
  q?: string
  a?: string
}

export const Route = createFileRoute("/_layout/journals/$journalId/ask")({
  validateSearch: (search: Record<string, unknown>): AskSearch => ({
    q: typeof search.q === "string" && search.q.trim() ? search.q : undefined,
    a: typeof search.a === "string" && search.a ? search.a : undefined,
  }),
  component: Ask,
  head: () => ({ meta: [{ title: "Ask - Resolve" }] }),
})

function Ask() {
  const { journalId } = Route.useParams()
  const { q, a } = Route.useSearch()
  return <AskPage journalId={journalId} question={q} articleId={a} />
}
