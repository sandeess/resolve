import { ArrowRight, ChevronDown, Search, X } from "lucide-react"
import { forwardRef } from "react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

export interface ScopeOption {
  id: string
  label: string
}

interface Props {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  placeholder?: string
  busy?: boolean
  size?: "hero" | "compact"
  /** Optional narrowing to one manuscript; "" means the whole journal. */
  scope?: {
    value: string
    options: ScopeOption[]
    onChange: (id: string) => void
  }
  autoFocus?: boolean
}

/** A big, rounded, Google-style search field. Press "/" anywhere to focus it. */
export const SearchBox = forwardRef<HTMLInputElement, Props>(function SearchBox(
  {
    value,
    onChange,
    onSubmit,
    placeholder,
    busy,
    size = "hero",
    scope,
    autoFocus,
  },
  ref,
) {
  const hero = size === "hero"
  const selected = scope?.options.find((o) => o.id === scope.value)
  const canSubmit = value.trim().length >= 3 && !busy

  return (
    // biome-ignore lint/a11y/useSemanticElements: explicit search landmark on the form
    <form
      role="search"
      className="w-full"
      onSubmit={(event) => {
        event.preventDefault()
        if (canSubmit) onSubmit()
      }}
    >
      <div
        className={cn(
          "group flex items-center gap-3 rounded-full border bg-card transition-shadow focus-within:border-transparent focus-within:shadow-e2 hover:shadow-e1",
          hero ? "h-14 px-6 sm:h-16" : "h-12 px-5",
        )}
      >
        <Search className="size-5 shrink-0 text-muted-foreground" />
        <input
          ref={(node) => {
            if (node && autoFocus && !node.dataset.focused) {
              node.dataset.focused = "1"
              node.focus()
            }
            if (typeof ref === "function") ref(node)
            else if (ref) ref.current = node
          }}
          data-hotkey-search
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder ?? "Ask a question"}
          aria-label="Question"
          autoComplete="off"
          enterKeyHint="search"
          className={cn(
            "min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground",
            hero ? "text-base sm:text-lg" : "text-base",
          )}
        />
        {value && (
          <button
            type="button"
            aria-label="Clear"
            onClick={() => onChange("")}
            className="rounded-full p-1.5 text-muted-foreground hover:bg-accent"
          >
            <X className="size-4" />
          </button>
        )}
        <button
          type="submit"
          disabled={!canSubmit}
          aria-label="Ask"
          className={cn(
            "flex shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-[opacity,transform,box-shadow] hover:shadow-e1 active:scale-95 disabled:pointer-events-none disabled:opacity-40",
            hero ? "size-10" : "size-9",
          )}
        >
          <ArrowRight className="size-5" />
        </button>
      </div>

      {scope && scope.options.length > 1 && (
        <div className={cn("mt-3 flex", hero && "justify-center")}>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex h-8 items-center gap-1.5 rounded-full border bg-card px-3.5 text-sm text-muted-foreground hover:bg-accent"
              >
                {selected?.label ?? "Whole journal"}
                <ChevronDown className="size-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align={hero ? "center" : "start"}
              className="w-72 rounded-2xl p-2"
            >
              {scope.options.map((option) => (
                <DropdownMenuItem
                  key={option.id || "all"}
                  className="rounded-xl py-2.5"
                  onClick={() => scope.onChange(option.id)}
                >
                  {option.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
    </form>
  )
})
