import { useQuery } from "@tanstack/react-query"

import { type TicketStatus, TicketsService } from "@/client"

/** Tickets of a journal, optionally one status. Shared so the page, the
 *  navigation badge and the command palette reuse one cached request. */
export function useTickets(
  journalId: string | undefined,
  status?: TicketStatus,
) {
  return useQuery({
    queryKey: ["tickets", journalId, status ?? "all"],
    enabled: Boolean(journalId),
    queryFn: async () =>
      (
        await TicketsService.listTickets({
          path: { journal_id: journalId as string },
          query: status ? { status } : undefined,
        })
      ).data,
  })
}
