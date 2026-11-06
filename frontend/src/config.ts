/** Where new people ask for an account (a Google Form). Empty hides the button. */
export const ACCESS_REQUEST_URL = (
  import.meta.env.VITE_ACCESS_REQUEST_URL ?? ""
).trim()

/** Fallback when there is no form: "Request access" opens a pre-filled email to this address. */
export const ACCESS_REQUEST_EMAIL = (
  import.meta.env.VITE_ACCESS_REQUEST_EMAIL ?? ""
).trim()

const REQUEST_BODY = [
  "Hello,",
  "",
  "I would like an account on Resolve.",
  "",
  "Name:",
  "Organisation:",
  "Journal(s) I work on:",
  "My role (author, editor, copyeditor, production, other):",
  "Why I need access:",
  "",
].join("\n")

export function accessRequestMailto(): string {
  const subject = encodeURIComponent("Resolve access request")
  return `mailto:${ACCESS_REQUEST_EMAIL}?subject=${subject}&body=${encodeURIComponent(REQUEST_BODY)}`
}

export const REPO_URL = "https://github.com/sandeess/resolve"

/** A Google Form shows cleanly inside an iframe only with `embedded=true`. */
export function embeddedFormUrl(url: string): string {
  if (!url.includes("docs.google.com/forms")) return url
  return url.includes("embedded=true")
    ? url
    : `${url}${url.includes("?") ? "&" : "?"}embedded=true`
}
