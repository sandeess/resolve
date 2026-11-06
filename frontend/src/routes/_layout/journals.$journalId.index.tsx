import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/journals/$journalId/")({
  beforeLoad: ({ params }) => {
    throw redirect({ to: "/journals/$journalId/ask", params, replace: true })
  },
})
