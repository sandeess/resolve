/** Where new people ask for an account (a Google Form). Empty hides the button. */
export const ACCESS_REQUEST_URL = (
  import.meta.env.VITE_ACCESS_REQUEST_URL ?? ""
).trim()

export const REPO_URL = "https://github.com/sandeess/resolve"

/** A Google Form shows cleanly inside an iframe only with `embedded=true`. */
export function embeddedFormUrl(url: string): string {
  if (!url.includes("docs.google.com/forms")) return url
  return url.includes("embedded=true")
    ? url
    : `${url}${url.includes("?") ? "&" : "?"}embedded=true`
}
