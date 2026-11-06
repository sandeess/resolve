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

const PROBLEMS = [
  {
    icon: UserRoundX,
    title: "One person holds the answers",
    text: "When they are away or leave, the office guesses, and the guesses differ.",
  },
  {
    icon: History,
    title: "The old stylesheet still ranks first",
    text: "Superseded rules stay in shared folders and keep getting quoted.",
  },
  {
    icon: Layers,
    title: "One journal's rule lands in another",
    text: "Each title has its own style, embargo and exceptions. Search does not respect that.",
  },
  {
    icon: MessagesSquare,
    title: "Decisions vanish into email",
    text: "The answer was agreed in a ticket last spring. The same question returns this month.",
  },
]

const HOW = [
  {
    n: "01",
    title: "Current files only",
    text: "Upload a revised stylesheet and it becomes the new version. The old one is kept for history and never used to answer.",
  },
  {
    n: "02",
    title: "Approved tickets only",
    text: "A lead approves a ticket answer and it becomes knowledge for everyone. Reopen it and it is withdrawn.",
  },
  {
    n: "03",
    title: "Cited, or silent",
    text: "Every claim points to the passage it came from. If the sources do not answer, Resolve says so and offers a ticket.",
  },
]

const PROOF = [
  { value: "95.8%", label: "of 168 trap questions answered correctly" },
  { value: "0", label: "stale or wrong-journal answers in that run" },
  { value: "100%", label: "of unanswerable questions refused, not guessed" },
  { value: "1-2 s", label: "typical time to a cited answer" },
]

interface Props {
  onSignIn: () => void
}

/** Public front page shown before sign-in: the problem, the product, a way in. */
export function Landing({ onSignIn }: Props) {
  return (
    <div className="landing min-h-screen overflow-x-hidden text-slate-200">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-white px-3 py-2 text-black focus:not-sr-only focus:absolute focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      <header className="relative z-20 mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
        <span className="flex items-center gap-3 font-display text-lg font-medium text-white">
          <LogoMark className="size-8" /> Resolve
        </span>
        <nav className="flex items-center gap-2" aria-label="Account">
          <RequestAccess>
            {(open) => (
              <button
                type="button"
                onClick={open}
                className="landing-link hidden px-4 py-2 text-sm sm:inline-block"
              >
                Request access
              </button>
            )}
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
          <NetworkCanvas className="absolute top-0 right-0 -z-10 h-full w-full opacity-25 [mask-image:linear-gradient(to_right,transparent,black_35%)] lg:w-[64%] lg:opacity-100" />
          <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 pt-10 pb-24 sm:px-8 lg:min-h-[calc(100vh-5rem)] lg:grid-cols-[1.05fr_0.95fr] lg:pt-0 lg:pb-16">
            <div className="max-w-2xl">
              <p className="mb-5 font-mono text-xs tracking-[0.2em] text-cyan-300/90 uppercase">
                Editorial knowledge for publishing offices
              </p>
              <h1 className="font-display text-4xl leading-[1.05] font-medium text-white sm:text-6xl">
                Every editorial answer,
                <span className="landing-gradient-text">
                  {" "}
                  cited and current.
                </span>
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300">
                Resolve answers from each journal's latest stylesheets and from
                ticket answers a lead has approved. When it does not know, it
                says so, and the question becomes a ticket.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={onSignIn}
                  className="landing-btn landing-btn-primary"
                >
                  Sign in <ArrowRight className="size-4" />
                </button>
                <RequestAccess>
                  {(open) => (
                    <button
                      type="button"
                      onClick={open}
                      className="landing-btn landing-btn-ghost"
                    >
                      Request access
                    </button>
                  )}
                </RequestAccess>
              </div>
              <p className="mt-8 max-w-md font-mono text-xs leading-relaxed text-slate-400">
                Measured on 168 trap questions (stale revisions, other journals,
                unapproved tickets): 0 stale or wrong-journal answers. Synthetic
                corpus.
              </p>
            </div>
            <div className="flex justify-center lg:justify-end">
              <AnswerDemo />
            </div>
          </div>
        </section>

        {/* Problem */}
        <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
          <p className="font-mono text-xs tracking-[0.2em] text-cyan-300/90 uppercase">
            The problem
          </p>
          <h2 className="mt-3 max-w-3xl font-display text-3xl font-medium text-white sm:text-4xl">
            Publishing runs on rules. The rules live in one person's head.
          </h2>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PROBLEMS.map(({ icon: Icon, title, text }) => (
              <article key={title} className="landing-card landing-lift p-6">
                <Icon className="size-6 text-amber-300" />
                <h3 className="mt-5 text-lg font-medium text-white">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">
                  {text}
                </p>
              </article>
            ))}
          </div>
        </section>

        {/* How it answers */}
        <section className="border-y border-white/10 bg-white/[0.02]">
          <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
            <p className="font-mono text-xs tracking-[0.2em] text-cyan-300/90 uppercase">
              How Resolve answers
            </p>
            <h2 className="mt-3 max-w-3xl font-display text-3xl font-medium text-white sm:text-4xl">
              It only knows what you have approved, and only the latest of it.
            </h2>
            <div className="mt-12 grid gap-4 lg:grid-cols-3">
              {HOW.map(({ n, title, text }) => (
                <article key={n} className="landing-card landing-lift p-7">
                  <span className="font-mono text-sm text-cyan-300">{n}</span>
                  <h3 className="mt-4 text-xl font-medium text-white">
                    {title}
                  </h3>
                  <p className="mt-3 leading-relaxed text-slate-400">{text}</p>
                </article>
              ))}
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <article className="landing-card flex gap-4 p-6">
                <ShieldCheck className="mt-0.5 size-6 shrink-0 text-cyan-300" />
                <p className="text-sm leading-relaxed text-slate-400">
                  <strong className="font-medium text-white">
                    Journal by journal.
                  </strong>{" "}
                  Another title's rules are invisible, enforced in the database,
                  not just in the interface.
                </p>
              </article>
              <article className="landing-card flex gap-4 p-6">
                <BookOpenCheck className="mt-0.5 size-6 shrink-0 text-cyan-300" />
                <p className="text-sm leading-relaxed text-slate-400">
                  <strong className="font-medium text-white">
                    Works in your AI tools.
                  </strong>{" "}
                  An MCP server with real sign-in gives Claude the same fenced
                  access as the person using it.
                </p>
              </article>
            </div>
          </div>
        </section>

        {/* Proof */}
        <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
          <p className="font-mono text-xs tracking-[0.2em] text-cyan-300/90 uppercase">
            Measured, not promised
          </p>
          <dl className="mt-8 grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 sm:grid-cols-2 lg:grid-cols-4">
            {PROOF.map(({ value, label }) => (
              <div key={label} className="bg-[#070b12] p-7">
                <dt className="font-display text-4xl font-medium text-white">
                  {value}
                </dt>
                <dd className="mt-2 text-sm leading-relaxed text-slate-400">
                  {label}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-xs text-slate-500">
            From the evaluation harness on a synthetic publishing corpus; see
            the repository for the method and its limits.
          </p>
        </section>

        {/* Access */}
        <section className="mx-auto max-w-7xl px-5 pb-28 sm:px-8">
          <div className="landing-card relative overflow-hidden p-8 sm:p-12">
            <div className="landing-glow" aria-hidden="true" />
            <div className="relative flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-xl">
                <h2 className="font-display text-3xl font-medium text-white">
                  Need an account?
                </h2>
                <p className="mt-3 leading-relaxed text-slate-300">
                  Accounts are created by an administrator. Tell us who you are
                  and which journal you work on, and we will reply by email.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <RequestAccess>
                  {(open) => (
                    <button
                      type="button"
                      onClick={open}
                      className="landing-btn landing-btn-primary"
                    >
                      Request access <ArrowRight className="size-4" />
                    </button>
                  )}
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

      <footer className="border-t border-white/10">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-8 text-sm text-slate-500 sm:px-8">
          <span>Resolve · open source, MIT licence</span>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="landing-link flex items-center gap-2"
          >
            <Code2 className="size-4" /> Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
