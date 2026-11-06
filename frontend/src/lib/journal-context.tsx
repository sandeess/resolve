import { createContext, useContext, useMemo } from "react"

import type { JournalPublic } from "@/client"
import useAuth from "@/hooks/useAuth"

export interface JournalAccess {
  journal: JournalPublic
  /** Mirrors backend/app/domain/policy.py; the API remains the authority. */
  canUploadRules: boolean
  canUpload: boolean
  canWork: boolean
  canApprove: boolean
  isAdmin: boolean
}

const JournalContext = createContext<JournalAccess | null>(null)

export function JournalProvider({
  journal,
  children,
}: {
  journal: JournalPublic
  children: React.ReactNode
}) {
  const { user } = useAuth()
  const value = useMemo<JournalAccess>(() => {
    const isAdmin = Boolean(user?.is_admin)
    const canApprove = isAdmin || journal.role === "lead"
    const canWork = canApprove || journal.role === "assistant"
    return {
      journal,
      isAdmin,
      canApprove,
      canWork,
      canUploadRules: canApprove,
      canUpload: canWork,
    }
  }, [journal, user?.is_admin])
  return (
    <JournalContext.Provider value={value}>{children}</JournalContext.Provider>
  )
}

export function useJournalAccess(): JournalAccess {
  const value = useContext(JournalContext)
  if (!value) throw new Error("useJournalAccess must be used inside a journal")
  return value
}
