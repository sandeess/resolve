import { useEffect } from "react"

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el) return false
  return (
    el.tagName === "INPUT" ||
    el.tagName === "TEXTAREA" ||
    el.tagName === "SELECT" ||
    el.isContentEditable
  )
}

/** Global shortcuts: Ctrl/Cmd+K opens the palette; "/" jumps to search. */
export function useGlobalHotkeys(openPalette: () => void) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        openPalette()
        return
      }
      if (
        event.key === "/" &&
        !isTyping(event.target) &&
        !event.metaKey &&
        !event.ctrlKey
      ) {
        event.preventDefault()
        const search = document.querySelector<HTMLElement>(
          "[data-hotkey-search]",
        )
        if (search) search.focus()
        else openPalette()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [openPalette])
}
