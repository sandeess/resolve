import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Trash2, UserPlus, Users } from "lucide-react"
import { useState } from "react"

import { JournalsService, type MemberPublic, type Role } from "@/client"
import { PersonAvatar } from "@/components/Shell/PersonAvatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const ROLES: { value: Role; label: string; hint: string }[] = [
  {
    value: "lead",
    label: "Lead",
    hint: "Approves ticket answers and uploads stylesheets",
  },
  {
    value: "assistant",
    label: "Assistant",
    hint: "Works tickets and uploads content",
  },
  { value: "viewer", label: "Viewer", hint: "Can ask and read" },
]

const selectClass =
  "h-10 rounded-lg border bg-card px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"

interface Props {
  journalId: string
  journalName: string
}

/** Who can use this journal, and as what. Administrators only. */
export default function MembersPanel({ journalId, journalName }: Props) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<Role>("assistant")
  const queryKey = ["members", journalId]

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: async () =>
      (await JournalsService.listMembers({ path: { journal_id: journalId } }))
        .data,
  })

  const save = useMutation({
    mutationFn: (v: { email: string; role: Role }) =>
      JournalsService.setMember({ path: { journal_id: journalId }, body: v }),
    onSuccess: (_, v) => {
      showSuccessToast(`${v.email} is now a ${v.role}`)
      void queryClient.invalidateQueries({ queryKey })
    },
    onError: handleError.bind(showErrorToast),
  })

  const remove = useMutation({
    mutationFn: (member: MemberPublic) =>
      JournalsService.removeMember({
        path: { journal_id: journalId, user_id: member.user_id },
      }),
    onSuccess: (_, member) => {
      showSuccessToast(`${member.email} removed`)
      void queryClient.invalidateQueries({ queryKey })
    },
    onError: handleError.bind(showErrorToast),
  })

  const valid = /^\S+@\S+\.\S+$/.test(email.trim())
  const members = data ?? []

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl sm:text-3xl">People</h1>
        <p className="text-muted-foreground">
          Who can use {journalName}, and what they can do. Someone you add
          before they have signed in gets access the first time they do.
        </p>
      </header>

      <form
        className="flex flex-col gap-3 rounded-2xl border bg-card p-4 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault()
          if (!valid) return
          save.mutate(
            { email: email.trim(), role },
            { onSuccess: () => setEmail("") },
          )
        }}
      >
        <div className="grid flex-1 gap-2">
          <Label htmlFor="member-email">Email address</Label>
          <Input
            id="member-email"
            type="email"
            autoComplete="off"
            placeholder="name@publisher.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="member-role">Role</Label>
          <select
            id="member-role"
            className={selectClass}
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
        <LoadingButton type="submit" loading={save.isPending} disabled={!valid}>
          <UserPlus /> Add person
        </LoadingButton>
      </form>
      <p className="-mt-3 px-1 text-xs text-muted-foreground">
        {ROLES.find((r) => r.value === role)?.hint}.
      </p>

      <div className="overflow-hidden rounded-2xl border">
        {isLoading && (
          <div className="space-y-3 p-4">
            <Skeleton className="h-12 rounded-xl" />
            <Skeleton className="h-12 rounded-xl" />
          </div>
        )}
        {!isLoading && members.length === 0 && (
          <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <Users className="size-7" />
            </span>
            <h2 className="text-lg">No one has access yet</h2>
            <p className="max-w-sm text-sm text-muted-foreground">
              Add the first person above. Administrators always have access to
              every journal.
            </p>
          </div>
        )}
        {members.map((member) => (
          <div
            key={member.user_id}
            className="flex flex-wrap items-center gap-3 border-b px-4 py-3 last:border-0 hover:bg-accent/50"
          >
            <PersonAvatar
              email={member.email}
              name={member.full_name}
              className="size-10"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">
                {member.full_name || member.email}
              </p>
              {member.full_name && (
                <p className="truncate text-sm text-muted-foreground">
                  {member.email}
                </p>
              )}
            </div>
            {member.pending && (
              <Badge variant="outline" title="Has not signed in yet">
                Invited
              </Badge>
            )}
            <select
              aria-label={`Role of ${member.email}`}
              className={selectClass}
              value={member.role}
              disabled={save.isPending}
              onChange={(e) =>
                save.mutate({
                  email: member.email,
                  role: e.target.value as Role,
                })
              }
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Remove ${member.email}`}
              title="Remove from this journal"
              disabled={remove.isPending}
              onClick={() => {
                if (
                  window.confirm(
                    `Remove ${member.email} from ${journalName}? They keep their account but lose access to this journal.`,
                  )
                )
                  remove.mutate(member)
              }}
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}
