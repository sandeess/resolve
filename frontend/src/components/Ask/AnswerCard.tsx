import { Check, Copy, LifeBuoy, SearchX } from "lucide-react"
import { Fragment, useState } from "react"

import type { AskResult } from "@/client"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"

function seconds(ms: number) {
  return `${(ms / 1000).toFixed(1)}s`
}

/** Renders "[2]" markers as small blue chips that jump to the matching source. */
function AnswerText({
  text,
  onCite,
}: {
  text: string
  onCite: (n: number) => void
}) {
  return (
    <p className="text-lg leading-8 whitespace-pre-wrap sm:text-xl sm:leading-9">
      {text.split(/(\[\d+\])/g).map((part, index) => {
        const match = /^\[(\d+)\]$/.exec(part)
        if (!match) return <Fragment key={`${index}-t`}>{part}</Fragment>
        const n = Number(match[1])
        return (
          <button
            key={`${index}-${n}`}
            type="button"
            onClick={() => onCite(n)}
            aria-label={`Go to source ${n}`}
            className="mx-0.5 inline-flex h-6 min-w-6 -translate-y-0.5 items-center justify-center rounded-full bg-secondary px-1.5 align-middle text-xs font-semibold text-secondary-foreground transition-colors hover:bg-primary hover:text-primary-foreground"
          >
            {n}
          </button>
        )
      })}
    </p>
  )
}

function TimingNote({ result }: { result: AskResult }) {
  const t = result.timings
  if (!t) return null
  const label = t.cached
    ? "Instant: answered from a recent identical question"
    : `Answered in ${seconds(t.total_ms)} · understanding ${seconds(t.embed_ms ?? 0)}, searching ${seconds(t.search_ms ?? 0)}, writing ${seconds(t.generate_ms ?? 0)}`
  return <p className="text-xs text-muted-foreground">{label}</p>
}

export function AnswerCard({
  result,
  onCite,
  onRaiseTicket,
  raising,
  onRephrase,
}: {
  result: AskResult
  onCite: (n: number) => void
  onRaiseTicket: () => void
  raising: boolean
  onRephrase: () => void
}) {
  const [copied, setCopied] = useState(false)

  if (result.abstained) {
    return (
      <section
        aria-live="polite"
        className="flex flex-col items-center gap-4 rounded-3xl bg-muted/60 px-6 py-10 text-center"
      >
        <span className="flex size-14 items-center justify-center rounded-full bg-card text-muted-foreground shadow-e1">
          <SearchX className="size-7" />
        </span>
        <div className="max-w-md space-y-1.5">
          <h2 className="text-xl">We couldn't find that in the documents</h2>
          <p className="text-muted-foreground">
            Nothing in this journal's current files or approved answers covers
            it
            {result.reason ? ` (${result.reason})` : ""}. Ask the team and the
            answer will be saved for next time.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <LoadingButton loading={raising} onClick={onRaiseTicket}>
            <LifeBuoy /> Raise a ticket
          </LoadingButton>
          <Button variant="ghost" onClick={onRephrase}>
            Rephrase the question
          </Button>
        </div>
        <TimingNote result={result} />
      </section>
    )
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(
        result.answer.replace(/\[\d+\]/g, "").replace(/\s+([.,;])/g, "$1"),
      )
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      // Clipboard blocked: nothing useful to tell the user.
    }
  }

  return (
    <section
      aria-live="polite"
      className="flex flex-col gap-4 rounded-3xl bg-secondary/40 p-6 sm:p-8"
    >
      <AnswerText text={result.answer} onCite={onCite} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TimingNote result={result} />
        <Button
          variant="ghost"
          size="sm"
          onClick={copy}
          aria-label="Copy answer"
        >
          {copied ? <Check className="text-success" /> : <Copy />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
    </section>
  )
}
