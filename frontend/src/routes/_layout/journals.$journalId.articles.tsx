import { createFileRoute } from "@tanstack/react-router"

import ArticlesPanel from "@/components/Journals/ArticlesPanel"
import { useJournalAccess } from "@/lib/journal-context"

export const Route = createFileRoute("/_layout/journals/$journalId/articles")({
  component: Articles,
  head: () => ({ meta: [{ title: "Articles - Resolve" }] }),
})

function Articles() {
  const { journalId } = Route.useParams()
  const { canUpload } = useJournalAccess()
  return <ArticlesPanel journalId={journalId} canCreate={canUpload} />
}
