import { ExternalLink } from "lucide-react"
import { type ReactNode, useState } from "react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { ACCESS_REQUEST_URL, embeddedFormUrl } from "@/config"

/**
 * "Request access": opens the Google Form in a dialog, so a new person can ask for an
 * account without leaving the page. Renders nothing when no form is configured.
 */
export function RequestAccess({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  if (!ACCESS_REQUEST_URL) return null
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className={className}>
        {children}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl gap-3 p-0 sm:max-w-2xl">
          <div className="px-6 pt-6">
            <DialogTitle className="text-xl">Request access</DialogTitle>
            <DialogDescription>
              Tell us who you are and which journal you work on. An
              administrator creates your account and replies by email.
            </DialogDescription>
          </div>
          <iframe
            title="Request access form"
            src={embeddedFormUrl(ACCESS_REQUEST_URL)}
            className="h-[62vh] w-full border-0"
            loading="lazy"
          >
            Loading…
          </iframe>
          <a
            href={ACCESS_REQUEST_URL}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-center gap-2 px-6 pb-5 text-sm text-muted-foreground underline-offset-4 hover:underline"
          >
            Form not showing? Open it in a new tab
            <ExternalLink className="size-3.5" />
          </a>
        </DialogContent>
      </Dialog>
    </>
  )
}
