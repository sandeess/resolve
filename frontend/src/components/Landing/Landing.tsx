import {
  ArrowRight,
  BookOpenCheck,
  Code2,
  History,
  Layers,
  MessagesSquare,
  ShieldCheck,
  UserRoundX,
} from "lucide-react"

import { LogoMark } from "@/components/Common/Logo"
import { ACCESS_REQUEST_URL, REPO_URL } from "@/config"
import { AnswerDemo } from "./AnswerDemo"
import { NetworkCanvas } from "./NetworkCanvas"
import { RequestAccess } from "./RequestAccess"

const PROOF = [
  { value: "95.8%", label: "of 168 trap questions answered correctly" },
  { value: "0", label: "stale or wrong-journal answers in that run" },
  { value: "100%", label: "of unanswerable questions refused, not guessed" },
  { value: "1-2 s", label: "typical time to a cited answer" },
]

const COSTS = [
  {
    icon: MessagesSquare,
    title: "The same question, answered again",
    text: "The answer was agreed in a ticket last spring. It returns to the inbox this month.",
  },
  {
    icon: History,
    title: "Retired rules still get quoted",
    text: "A superseded stylesheet stays in a shared folder and ranks first in search.",
  },
  {
    icon: UserRoundX,
    title: "One person holds the answers",
    text: "When they are away or leave, the office guesses, and the guesses differ.",
  },
]

const HOW = [
  {
    n: "01",
    title: "Answers from current files only",
    text: "Upload a revised stylesheet and it becomes the new version. The old one is kept for history and never used to answer.",
  },
  {
    n: "02",
    title: "Answers from approved tickets only",
    text: "A lead approves a ticket answer and it becomes knowledge for everyone. Reopen it and it is withdrawn.",
  },
  {
    n: "03",
    title: "Citations, or a clear refusal",
    text: "Every claim points to the passage it came from. If the sources do not answer, Resolve says so and offers a ticket.",
  },
]

const CONTROL = [
  {
    icon: ShieldCheck,
    title: "Journal by journal",
    text: "Another title's rules are invisible, enforced in the database, not just in the interface.",
  },
  {
    icon: Layers,
    title: "Full version history",
    text: "Every stylesheet revision and every ticket decision is kept, so an answer can be traced.",
  },
  {
    icon: BookOpenCheck,
    title: "Works in your AI tools",
    text: "An MCP server with real sign-in gives Claude the same fenced access as the person using it.",
  },
]

const EYEBROW = "text-sm font-medium text-[#d9b26a]"
const H2 =
  "landing-serif mt-3 max-w-3xl text-3xl leading-tight text-[#f3efe6] sm:text-4xl"

interface Props {
  onSignIn: () => void
}

/** Public front page shown before sign-in: the outcome, the proof, a way in. */
export function Landing({ onSignIn }: Props) {
  return (
    <div className="landing min-h-screen overflow-x-hidden text-[#cfc9bb]">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-white px-3 py-2 text-black focus:not-sr-only focus:absolute focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      <header className="relative z-20 mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
        <span className="flex items-center gap-3 text-lg font-medium text-[#f3efe6]">
          <LogoMark className="size-8" /> Resolve
        </span>
        <nav className="flex items-center gap-2" aria-label="Account">
          <RequestAccess className="landing-link hidden px-4 py-3 text-sm min-[420px]:inline-block">
            Request access
          </RequestAccess>
          <button
            type="button"
            onClick={onSignIn}
            className="landing-btn landing-btn-ghost"
          >
            Sign in
          </button>
        </nav>
      </header>

      <main id="main">
        {/* Hero */}
        <section className="relative isolate">
          <div
            className="landing-grid absolute inset-0 -z-10"
            aria-hidden="true"
          />
          <NetworkCanvas className="absolute top-0 right-0 -z-10 h-full w-full opacity-20 [mask-image:linear-gradient(to_right,transparent,black_35%)] lg:w-[64%] lg:opacity-90" />
          <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 pt-10 pb-20 sm:px-8 lg:min-h-[calc(100vh-5rem)] lg:grid-cols-[1.05fr_0.95fr] lg:pt-0 lg:pb-16">
            <div className="max-w-2xl">
              <p className={`mb-5 ${EYEBROW}`}>
                For publishing offices and journal teams
              </p>
              <h1 className="landing-serif text-4xl leading-[1.06] text-[#f3efe6] sm:text-6xl">
                Editorial answers,
                <span className="landing-gradient-text">
                  {" "}
                  cited and current.
                </span>
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-[#cfc9bb]">
                Resolve answers from each journal's latest stylesheets and from
                ticket answers a lead has approved. When the sources do not
                answer, it says so and the question becomes a ticket.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <RequestAccess className="landing-btn landing-btn-primary">
                  Request access <ArrowRight className="size-4" />
                </RequestAccess>
                <button
                  type="button"
                  onClick={onSignIn}
                  className="landing-btn landing-btn-ghost"
                >
                  Sign in
                </button>
              </div>
            </div>
            <div className="flex justify-center lg:justify-end">
              <AnswerDemo />
            </div>
          </div>
        </section>

        {/* Proof */}
        <section className="mx-auto max-w-7xl px-5 pb-24 sm:px-8">
          <dl className="grid gap-px overflow-hidden rounded-2xl border border-[#f3efe6]/10 bg-[#f3efe6]/10 sm:grid-cols-2 lg:grid-cols-4">
            {PROOF.map(({ value, label }) => (
              <div key={label} className="bg-[#0a0e18] p-7">
                <dt className="landing-serif text-4xl text-[#d9b26a] sm:text-5xl">
                  {value}
                </dt>
                <dd className="mt-3 text-base leading-relaxed text-[#cfc9bb]">
                  {label}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-sm text-slate-400">
            Measured on 168 trap questions covering stale revisions, other
            journals and unapproved tickets. Synthetic publishing corpus; the
            repository documents the method and its limits.
          </p>
        </section>

        {/* Cost */}
        <section className="mx-auto max-w-7xl px-5 pb-24 sm:px-8">
          <p className={EYEBROW}>The cost of unanswered rules</p>
          <h2 className={H2}>
            Publishing runs on rules. The rules live in one person's head.
          </h2>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {COSTS.map(({ icon: Icon, title, text }) => (
              <article key={title} className="landing-card landing-lift p-7">
                <Icon className="size-6 text-[#d9b26a]" />
                <h3 className="mt-5 text-xl font-medium text-[#f3efe6]">
                  {title}
                </h3>
                <p className="mt-2 text-base leading-relaxed text-[#cfc9bb]">
                  {text}
                </p>
              </article>
            ))}
          </div>
        </section>

        {/* How it answers */}
        <section className="border-y border-[#f3efe6]/10 bg-[#f3efe6]/[0.02]">
          <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
            <p className={EYEBROW}>How Resolve answers</p>
            <h2 className={H2}>
              It knows only what you have approved, and only the latest of it.
            </h2>
            <div className="mt-12 grid gap-4 lg:grid-cols-3">
              {HOW.map(({ n, title, text }) => (
                <article key={n} className="landing-card landing-lift p-7">
                  <span className="landing-serif text-lg text-[#d9b26a]">
                    {n}
                  </span>
                  <h3 className="mt-4 text-xl font-medium text-[#f3efe6]">
                    {title}
                  </h3>
                  <p className="mt-3 text-base leading-relaxed text-[#cfc9bb]">
                    {text}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Control */}
        <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
          <p className={EYEBROW}>Control and traceability</p>
          <h2 className={H2}>
            Built so each answer can be checked and traced.
          </h2>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {CONTROL.map(({ icon: Icon, title, text }) => (
              <article key={title} className="landing-card flex gap-4 p-7">
                <Icon className="mt-0.5 size-6 shrink-0 text-[#d9b26a]" />
                <div>
                  <h3 className="text-lg font-medium text-[#f3efe6]">
                    {title}
                  </h3>
                  <p className="mt-2 text-base leading-relaxed text-[#cfc9bb]">
                    {text}
                  </p>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* Access */}
        <section className="mx-auto max-w-7xl px-5 pb-28 sm:px-8">
          <div className="landing-card relative overflow-hidden p-8 sm:p-12">
            <div className="landing-glow" aria-hidden="true" />
            <div className="relative flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-xl">
                <h2 className="landing-serif text-3xl text-[#f3efe6]">
                  Need an account?
                </h2>
                <p className="mt-3 text-lg leading-relaxed text-[#cfc9bb]">
                  Accounts are created by an administrator. Tell us who you are
                  and which journal you work on, and we will reply by email.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <RequestAccess className="landing-btn landing-btn-primary">
                  Request access <ArrowRight className="size-4" />
                </RequestAccess>
                <button
                  type="button"
                  onClick={onSignIn}
                  className="landing-btn landing-btn-ghost"
                >
                  {ACCESS_REQUEST_URL ? "I have an account" : "Sign in"}
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#f3efe6]/10">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-8 text-sm text-slate-400 sm:px-8">
          <span>
            Resolve · a{" "}
            <a
              href="https://sortitouthq.com"
              className="landing-link py-3"
              rel="noreferrer"
            >
              sortitouthq
            </a>{" "}
            product · open source, MIT licence
          </span>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="landing-link flex items-center gap-2 py-3"
          >
            <Code2 className="size-4" /> Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
