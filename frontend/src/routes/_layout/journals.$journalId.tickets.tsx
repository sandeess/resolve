import { createFileRoute, Outlet } from "@tanstack/react-router"

// Parent of the ticket list and ticket detail so both share the journal context.
export const Route = createFileRoute("/_layout/journals/$journalId/tickets")({
  component: Outlet,
})
