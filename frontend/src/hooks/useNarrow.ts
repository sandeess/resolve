import { useEffect, useState } from "react"

/** True on phone-sized screens (matches Tailwind's `sm` breakpoint, 640px). */
export function useNarrow(): boolean {
  const query = "(max-width: 639px)"
  const [narrow, setNarrow] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  )
  useEffect(() => {
    const media = window.matchMedia(query)
    const update = () => setNarrow(media.matches)
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [])
  return narrow
}
