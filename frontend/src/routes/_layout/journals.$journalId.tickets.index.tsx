import { createFileRoute } from "@tanstack/react-router"

import TicketsPanel from "@/components/Tickets/TicketsPanel"

export const Route = createFileRoute("/_layout/journals/$journalId/tickets/")({
  component: () => <TicketsPanel journalId={Route.useParams().journalId} />,
  head: () => ({ meta: [{ title: "Tickets - Resolve" }] }),
})
