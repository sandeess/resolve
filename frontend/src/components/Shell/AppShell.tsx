import { Menu, Search } from "lucide-react"
import { useCallback, useState } from "react"

import { Logo } from "@/components/Common/Logo"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet"
import { CommandPalette } from "./CommandPalette"
import { useGlobalHotkeys } from "./hotkeys"
import { NavRail } from "./NavRail"
import { ThemeToggle } from "./ThemeToggle"
import { UserMenu } from "./UserMenu"

const isMac =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform)

/** Top bar, left navigation and content frame, in the style of Google's apps. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const openPalette = useCallback(() => setPaletteOpen(true), [])
  useGlobalHotkeys(openPalette)

  return (
    <div className="min-h-svh bg-background">
      <a
        href="#content"
        className="sr-only z-[60] rounded-full bg-primary px-4 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-30 flex h-16 items-center gap-2 bg-background/90 px-3 backdrop-blur md:px-4">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          aria-label="Open navigation"
          onClick={() => setDrawerOpen(true)}
        >
          <Menu />
        </Button>
        <div className="lg:w-64">
          <Logo />
        </div>

        <button
          type="button"
          onClick={openPalette}
          className="mx-auto hidden h-12 w-full max-w-2xl items-center gap-3 rounded-full bg-muted px-5 text-left text-muted-foreground transition-[background-color,box-shadow] hover:bg-card hover:shadow-e1 focus-visible:bg-card focus-visible:shadow-e1 sm:flex"
          aria-label="Search or ask (opens the command palette)"
        >
          <Search className="size-5" />
          <span className="flex-1 truncate">
            Ask a question or jump to anything
          </span>
          <kbd className="rounded-md border bg-background/60 px-2 py-0.5 text-xs">
            {isMac ? "⌘" : "Ctrl"} K
          </kbd>
        </button>

        <div className="ml-auto flex items-center gap-1 sm:ml-0">
          <Button
            variant="ghost"
            size="icon"
            className="sm:hidden"
            aria-label="Search or ask"
            onClick={openPalette}
          >
            <Search />
          </Button>
          <ThemeToggle />
          <UserMenu />
        </div>
      </header>

      <div className="flex gap-2 px-0 pb-4 lg:px-3">
        <aside className="sticky top-16 hidden h-[calc(100svh-4.5rem)] w-64 shrink-0 overflow-y-auto pr-1 lg:block">
          <NavRail />
        </aside>
        <main
          id="content"
          className="min-h-[calc(100svh-5rem)] min-w-0 flex-1 bg-card px-4 py-6 sm:px-8 sm:py-8 lg:rounded-3xl lg:border"
        >
          <div className="mx-auto w-full max-w-5xl">{children}</div>
        </main>
      </div>

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left" className="w-[19rem] gap-0 p-3">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">
            Pages in this journal
          </SheetDescription>
          <div className="px-2 pt-1 pb-4">
            <Logo />
          </div>
          <NavRail onNavigate={() => setDrawerOpen(false)} />
        </SheetContent>
      </Sheet>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  )
}
