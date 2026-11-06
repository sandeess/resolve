import { createFileRoute } from "@tanstack/react-router"
import { ShieldAlert } from "lucide-react"

import MembersPanel from "@/components/Journals/MembersPanel"
import { useJournalAccess } from "@/lib/journal-context"

export const Route = createFileRoute("/_layout/journals/$journalId/members")({
  component: Members,
  head: () => ({ meta: [{ title: "People - Resolve" }] }),
})

function Members() {
  const { journalId } = Route.useParams()
  const { journal, isAdmin } = useJournalAccess()
  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <ShieldAlert className="size-10 text-muted-foreground" />
        <h1 className="text-xl">Only administrators manage people</h1>
        <p className="max-w-sm text-muted-foreground">
          Ask an administrator to add or change who can use this journal.
        </p>
      </div>
    )
  }
  return <MembersPanel journalId={journalId} journalName={journal.name} />
}
