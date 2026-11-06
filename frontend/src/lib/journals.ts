import { useQuery } from "@tanstack/react-query"

import { JournalsService, TicketsService } from "@/client"
import { readStored, writeStored } from "./storage"

const LAST_JOURNAL_KEY = "resolve:last-journal"

export function useJournals() {
  return useQuery({
    queryKey: ["journals"],
    queryFn: async () => (await JournalsService.listJournals()).data,
  })
}

export function useJournal(journalId: string) {
  return useQuery({
    queryKey: ["journal", journalId],
    queryFn: async () =>
      (await JournalsService.readJournal({ path: { journal_id: journalId } }))
        .data,
  })
}

/** Open tickets in a journal (powers the badge in the navigation). */
export function useOpenTicketCount(journalId: string | undefined) {
  return useQuery({
    queryKey: ["tickets", journalId, "open"],
    enabled: Boolean(journalId),
    queryFn: async () =>
      (
        await TicketsService.listTickets({
          path: { journal_id: journalId as string },
          query: { status: "open" },
        })
      ).data.count,
  })
}

export const lastJournal = {
  get: () => readStored<string | null>(LAST_JOURNAL_KEY, null),
  set: (id: string) => writeStored(LAST_JOURNAL_KEY, id),
}
