// Google-ish avatar colours; the same person always gets the same one.
const COLOURS = [
  "#1a73e8",
  "#d93025",
  "#188038",
  "#e37400",
  "#9334e6",
  "#129eaf",
  "#c5221f",
  "#3367d6",
]

export function avatarColour(seed: string): string {
  let hash = 0
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return COLOURS[hash % COLOURS.length]
}

export function initials(nameOrEmail: string): string {
  const name = nameOrEmail
    .split("@")[0]
    .replace(/[._-]+/g, " ")
    .trim()
  const parts = name.split(/\s+/).filter(Boolean)
  const letters =
    parts.length > 1
      ? parts[0][0] + parts[parts.length - 1][0]
      : name.slice(0, 2)
  return letters.toUpperCase()
}
