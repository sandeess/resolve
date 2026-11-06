import { createFileRoute } from "@tanstack/react-router"

import DocumentsPanel from "@/components/Journals/DocumentsPanel"
import { useJournalAccess } from "@/lib/journal-context"

export const Route = createFileRoute("/_layout/journals/$journalId/documents")({
  component: Documents,
  head: () => ({ meta: [{ title: "Documents - Resolve" }] }),
})

function Documents() {
  const { journalId } = Route.useParams()
  const access = useJournalAccess()
  return (
    <DocumentsPanel
      journalId={journalId}
      canUploadRules={access.canUploadRules}
      canUpload={access.canUpload}
    />
  )
}
