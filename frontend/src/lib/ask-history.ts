import { useCallback, useState } from "react"

import { readStored, writeStored } from "./storage"

const MAX = 8
const key = (journalId: string) => `resolve:ask-history:${journalId}`

/** The last few questions asked in a journal, kept in this browser only. */
export function useAskHistory(journalId: string) {
  const [items, setItems] = useState<string[]>(() =>
    readStored<string[]>(key(journalId), []),
  )

  const remember = useCallback(
    (question: string) => {
      const q = question.trim()
      if (!q) return
      setItems((current) => {
        const next = [q, ...current.filter((c) => c !== q)].slice(0, MAX)
        writeStored(key(journalId), next)
        return next
      })
    },
    [journalId],
  )

  const forget = useCallback(() => {
    writeStored(key(journalId), [])
    setItems([])
  }, [journalId])

  return { items, remember, forget }
}
