import { Pause, Play, Sparkles } from "lucide-react"
import { useEffect, useState } from "react"

interface Example {
  question: string
  answer: string
  sources: string[]
  abstains?: boolean
}

// Illustrative examples, not real data. The third shows an article-level
// exception overriding the journal-wide rule.
const EXAMPLES: Example[] = [
  {
    question: "How long may the abstract be?",
    answer: "The abstract may be 150 words [1].",
    sources: ["Stylesheet · version 3 · Abstracts"],
  },
  {
    question: "Is a cover letter required?",
    answer: "I can't find this in the current files.",
    sources: [],
    abstains: true,
  },
  {
    question: "Which reference style applies to JNL-101?",
    answer: "Author-date [1]. An extended list was agreed for JNL-101 [2].",
    sources: ["Stylesheet · version 3 · References", "Ticket T-12 · approved"],
  },
]

type Phase = "question" | "thinking" | "answer" | "hold"

const TYPE_MS = 28

/** One looping Q&A card. Pauses on hover and with its own button. */
export function AnswerDemo() {
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  const [index, setIndex] = useState(0)
  const [phase, setPhase] = useState<Phase>(reduced ? "hold" : "question")
  const [typed, setTyped] = useState(reduced ? EXAMPLES[0].question.length : 0)
  const [paused, setPaused] = useState(false)
  const [hovered, setHovered] = useState(false)
  const example = EXAMPLES[index]
  const running = !reduced && !paused && !hovered

  useEffect(() => {
    if (!running) return
    let timer: ReturnType<typeof setTimeout>
    if (phase === "question") {
      timer = setTimeout(
        () =>
          typed < example.question.length
            ? setTyped(typed + 1)
            : setPhase("thinking"),
        typed < example.question.length ? TYPE_MS : 250,
      )
    } else if (phase === "thinking") {
      timer = setTimeout(() => setPhase("answer"), 650)
    } else if (phase === "answer") {
      timer = setTimeout(() => setPhase("hold"), 450)
    } else {
      timer = setTimeout(() => {
        setIndex((index + 1) % EXAMPLES.length)
        setTyped(0)
        setPhase("question")
      }, 3200)
    }
    return () => clearTimeout(timer)
  }, [running, phase, typed, example.question.length, index])

  const showAnswer = phase === "answer" || phase === "hold"
  const question = example.question.slice(0, typed)

  return (
    <section
      aria-label="Example question and answer"
      className="landing-card w-full max-w-md"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <span className="flex items-center gap-2 font-mono text-xs tracking-wide text-[#e8cd94] uppercase">
          <Sparkles className="size-3.5" /> Example
        </span>
        {!reduced && (
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            aria-label={paused ? "Play the example" : "Pause the example"}
            className="-m-2 rounded-full p-3 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
          >
            {paused ? (
              <Play className="size-4" />
            ) : (
              <Pause className="size-4" />
            )}
          </button>
        )}
      </div>

      <div className="min-h-[15.5rem] space-y-4 p-5">
        <p className="font-mono text-[0.95rem] leading-relaxed text-slate-100">
          <span className="text-[#d9b26a]">&gt; </span>
          {question}
          {phase === "question" && (
            <span className="landing-caret" aria-hidden="true" />
          )}
        </p>

        {phase === "thinking" && (
          <p className="flex gap-1.5 pl-5" role="status">
            <span className="sr-only">Thinking</span>
            <span className="landing-dot" />
            <span className="landing-dot [animation-delay:150ms]" />
            <span className="landing-dot [animation-delay:300ms]" />
          </p>
        )}

        {showAnswer && (
          <div className="space-y-3 pl-5" aria-live="polite">
            <p
              className={
                example.abstains
                  ? "text-[0.95rem] leading-relaxed text-slate-300"
                  : "text-[0.95rem] leading-relaxed text-white"
              }
            >
              {example.answer}
            </p>
            {example.abstains ? (
              <span className="inline-flex rounded-full border border-[#d9b26a]/40 px-3 py-1 text-xs text-slate-300">
                Raise a ticket
              </span>
            ) : (
              <ul className="space-y-1.5">
                {example.sources.map((source, i) => (
                  <li
                    key={source}
                    className="flex items-start gap-2 font-mono text-xs text-slate-400"
                  >
                    <span className="mt-px rounded bg-[#d9b26a]/15 px-1.5 text-[#e8cd94]">
                      {i + 1}
                    </span>
                    {source}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
