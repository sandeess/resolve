import { useNavigate, useParams } from "@tanstack/react-router"
import { Command } from "cmdk"
import {
  BookOpen,
  CornerDownLeft,
  FileText,
  Home,
  LifeBuoy,
  LogOut,
  Moon,
  Search,
  Sparkles,
  Sun,
  Users,
} from "lucide-react"
import { useEffect, useState } from "react"

import { useTheme } from "@/components/theme-provider"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import useAuth from "@/hooks/useAuth"
import { lastJournal, useJournals } from "@/lib/journals"
import { useTickets } from "@/lib/tickets"

const itemClass =
  "flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-foreground/90 data-[selected=true]:bg-secondary data-[selected=true]:text-secondary-foreground [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-muted-foreground data-[selected=true]:[&_svg]:text-secondary-foreground"
const groupClass =
  "[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-muted-foreground [&_[cmdk-group-heading]]:uppercase"

/** Ctrl/Cmd+K: ask a question, jump to a page or ticket, switch theme, all from the keyboard. */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const { journalId: routeJournal } = useParams({ strict: false }) as {
    journalId?: string
  }
  const { data: journals } = useJournals()
  const { setTheme } = useTheme()
  const { logout, user } = useAuth()
  const [text, setText] = useState("")

  // Ask goes to the journal you are in, else the one you used last, else the first.
  const target =
    routeJournal ??
    journals?.data.find((j) => j.id === lastJournal.get())?.id ??
    journals?.data[0]?.id
  const tickets = useTickets(routeJournal)

  useEffect(() => {
    if (!open) setText("")
  }, [open])

  const go = (action: () => void) => {
    onOpenChange(false)
    action()
  }
  const question = text.trim()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="top-[16%] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-xl"
      >
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">
          Ask a question, jump to a page or ticket, or change settings.
        </DialogDescription>
        <Command label="Command palette" loop>
          <div className="flex items-center gap-3 border-b px-4">
            <Search className="size-5 text-muted-foreground" />
            <Command.Input
              value={text}
              onValueChange={setText}
              placeholder="Ask a question or jump to..."
              className="h-14 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
            />
            <kbd className="rounded-md border px-1.5 py-0.5 text-xs text-muted-foreground">
              Esc
            </kbd>
          </div>
          <Command.List className="max-h-[min(60vh,420px)] overflow-y-auto p-2">
            <Command.Empty className="px-3 py-8 text-center text-sm text-muted-foreground">
              Nothing matches "{text}".
            </Command.Empty>

            {question.length >= 3 && target && (
              <Command.Group forceMount className={groupClass} heading="Ask">
                <Command.Item
                  forceMount
                  value={`ask ${question}`}
                  className={itemClass}
                  onSelect={() =>
                    go(
                      () =>
                        void navigate({
                          to: "/journals/$journalId/ask",
                          params: { journalId: target },
                          search: { q: question },
                        }),
                    )
                  }
                >
                  <Sparkles />
                  <span className="min-w-0 flex-1 truncate">
                    Ask: "{question}"
                  </span>
                  <CornerDownLeft />
                </Command.Item>
              </Command.Group>
            )}

            <Command.Group className={groupClass} heading="Go to">
              <Command.Item
                className={itemClass}
                value="home"
                onSelect={() => go(() => void navigate({ to: "/" }))}
              >
                <Home /> Home
              </Command.Item>
              {routeJournal &&
                (
                  [
                    ["Ask", Sparkles, "/journals/$journalId/ask"],
                    ["Tickets", LifeBuoy, "/journals/$journalId/tickets"],
                    ["Documents", FileText, "/journals/$journalId/documents"],
                    ["Articles", BookOpen, "/journals/$journalId/articles"],
                    ...(user?.is_admin
                      ? ([
                          ["People", Users, "/journals/$journalId/members"],
                        ] as const)
                      : []),
                  ] as const
                ).map(([label, Icon, to]) => (
                  <Command.Item
                    key={label}
                    value={`go ${label}`}
                    className={itemClass}
                    onSelect={() =>
                      go(
                        () =>
                          void navigate({
                            to,
                            params: { journalId: routeJournal },
                          }),
                      )
                    }
                  >
                    <Icon /> {label}
                  </Command.Item>
                ))}
              {journals?.data.map((j) => (
                <Command.Item
                  key={j.id}
                  value={`journal ${j.code} ${j.name}`}
                  className={itemClass}
                  onSelect={() =>
                    go(
                      () =>
                        void navigate({
                          to: "/journals/$journalId/ask",
                          params: { journalId: j.id },
                        }),
                    )
                  }
                >
                  <BookOpen /> {j.name}
                  <span className="ml-auto text-xs text-muted-foreground">
                    {j.code}
                  </span>
                </Command.Item>
              ))}
            </Command.Group>

            {tickets.data && tickets.data.count > 0 && (
              <Command.Group className={groupClass} heading="Tickets">
                {tickets.data.data.slice(0, 30).map((t) => (
                  <Command.Item
                    key={t.id}
                    value={`ticket T-${t.number} ${t.title}`}
                    className={itemClass}
                    onSelect={() =>
                      go(
                        () =>
                          void navigate({
                            to: "/journals/$journalId/tickets/$ticketId",
                            params: { journalId: t.journal_id, ticketId: t.id },
                          }),
                      )
                    }
                  >
                    <LifeBuoy />
                    <span className="min-w-0 flex-1 truncate">{t.title}</span>
                    <span className="text-xs text-muted-foreground">
                      T-{t.number}
                    </span>
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            <Command.Group className={groupClass} heading="Settings">
              <Command.Item
                className={itemClass}
                value="theme light"
                onSelect={() => go(() => setTheme("light"))}
              >
                <Sun /> Light theme
              </Command.Item>
              <Command.Item
                className={itemClass}
                value="theme dark"
                onSelect={() => go(() => setTheme("dark"))}
              >
                <Moon /> Dark theme
              </Command.Item>
              <Command.Item
                className={itemClass}
                value="sign out"
                onSelect={() => go(() => void logout())}
              >
                <LogOut /> Sign out
              </Command.Item>
            </Command.Group>
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  )
}
