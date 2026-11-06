import { createFileRoute, Link, Outlet } from "@tanstack/react-router"
import { Lock } from "lucide-react"
import { useEffect } from "react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { JournalProvider } from "@/lib/journal-context"
import { lastJournal, useJournal } from "@/lib/journals"

export const Route = createFileRoute("/_layout/journals/$journalId")({
  component: JournalLayout,
})

/** Loads the journal once and shares it (with the user's permissions) with every section. */
function JournalLayout() {
  const { journalId } = Route.useParams()
  const { data: journal, isError, isLoading } = useJournal(journalId)

  useEffect(() => {
    if (journal) lastJournal.set(journal.id)
  }, [journal])

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full rounded-3xl" />
      </div>
    )
  }
  if (isError || !journal) {
    return (
      <div className="flex min-h-[50svh] flex-col items-center justify-center gap-4 text-center">
        <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Lock className="size-7" />
        </span>
        <h1 className="text-2xl">You don't have access to this journal</h1>
        <p className="max-w-sm text-muted-foreground">
          It may not exist, or an administrator hasn't added you yet.
        </p>
        <Button asChild>
          <Link to="/">Back to home</Link>
        </Button>
      </div>
    )
  }
  return (
    <JournalProvider journal={journal}>
      <Outlet />
    </JournalProvider>
  )
}
