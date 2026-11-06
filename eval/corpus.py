"""Synthetic publishing corpus and golden question set (seeded, no real data).

Every golden item carries `evidence`: the exact sentence that answers it. That
sentence is how we decide whether retrieval found the right passage, and it
includes the *value* (e.g. "TIFF"), so a stale revision of the same rule does
not count as a hit.

Trap types, each aimed at a failure the product must not have:

* ``stale``            the rule changed in v2; the v1 value must not appear
* ``fact``             an unchanged rule; other journals' values must not leak
* ``article``          an article-level exception, asked with that article
* ``article_isolation`` the same topic asked journal-wide must NOT see the exception
* ``ticket``           knowledge that exists only in an approved ticket
* ``unapproved_trap``  a resolved-but-unapproved ticket must not be used
* ``unanswerable``     nothing in the corpus answers it: the system must abstain
"""

import json
import random
from dataclasses import asdict, dataclass, field
from typing import Literal

Style = Literal["lexical", "paraphrase", "na"]
ItemType = Literal[
    "fact",
    "stale",
    "article",
    "article_isolation",
    "ticket",
    "unapproved_trap",
    "unanswerable",
]


@dataclass(frozen=True)
class Fact:
    key: str
    doc: Literal["stylesheet", "guideline"]
    heading: str
    sentence: str  # contains {v}
    values: tuple[str, ...]
    lexical: str  # shares keywords with the sentence
    paraphrase: str  # avoids the sentence's keywords


FACTS: tuple[Fact, ...] = (
    Fact(
        "references",
        "stylesheet",
        "References",
        "References must follow the {v} style and be listed at the end of the manuscript.",
        (
            "Harvard author-date",
            "Vancouver numbered",
            "APA seventh edition",
            "Chicago author-date",
        ),
        "Which style must references follow?",
        "How do I cite other people's work in the bibliography?",
    ),
    Fact(
        "figure_format",
        "stylesheet",
        "Figures",
        "Figures must be supplied as {v} files.",
        ("TIFF", "PNG", "EPS", "SVG"),
        "What file format must figures be supplied as?",
        "Which picture type do you want for the artwork?",
    ),
    Fact(
        "figure_dpi",
        "stylesheet",
        "Figures",
        "Raster figures need a resolution of at least {v}.",
        ("300 dpi", "450 dpi", "600 dpi", "1200 dpi"),
        "What resolution do raster figures need?",
        "How sharp does the artwork have to be?",
    ),
    Fact(
        "dates",
        "stylesheet",
        "Dates",
        "Write dates in the {v} format.",
        ("DD Month YYYY", "Month DD, YYYY", "YYYY-MM-DD", "DD/MM/YYYY"),
        "Which format should dates be written in?",
        "How do I write a calendar day in the text?",
    ),
    Fact(
        "spelling",
        "stylesheet",
        "Language",
        "Use {v} spelling throughout.",
        (
            "British English",
            "American English",
            "Canadian English",
            "Australian English",
        ),
        "Which spelling convention should be used?",
        "Should colour be spelled with a u?",
    ),
    Fact(
        "units",
        "stylesheet",
        "Units",
        "Report measurements using {v}.",
        (
            "SI units",
            "US customary units",
            "CGS units",
            "SI units with imperial equivalents",
        ),
        "What system of units should measurements use?",
        "Do we report distances in metres or miles?",
    ),
    Fact(
        "headings",
        "stylesheet",
        "Headings",
        "Use at most {v} of section headings.",
        ("two levels", "three levels", "four levels", "five levels"),
        "How many levels of section headings are allowed?",
        "How deeply can I nest subsections?",
    ),
    Fact(
        "tables",
        "stylesheet",
        "Tables",
        "Tables must be supplied as {v}.",
        ("editable Word tables", "Excel files", "LaTeX tabular code", "CSV files"),
        "How must tables be supplied?",
        "In what form do you want the data grids?",
    ),
    Fact(
        "abstract",
        "guideline",
        "Abstract",
        "Abstracts must not exceed {v}.",
        ("150 words", "200 words", "250 words", "300 words"),
        "What is the maximum abstract length?",
        "How long may the summary at the top be?",
    ),
    Fact(
        "keywords",
        "guideline",
        "Keywords",
        "Provide {v} after the abstract.",
        ("4 keywords", "5 keywords", "6 keywords", "8 keywords"),
        "How many keywords should be provided?",
        "How many index terms do I list under the summary?",
    ),
    Fact(
        "title",
        "guideline",
        "Title",
        "Titles are limited to {v}.",
        ("80 characters", "100 characters", "120 characters", "150 characters"),
        "What is the title length limit?",
        "How long can the name of my paper be?",
    ),
    Fact(
        "manuscript_format",
        "guideline",
        "Submission",
        "Submit the manuscript as {v}.",
        (
            "a Word document",
            "a LaTeX source archive",
            "a PDF with source files",
            "a Markdown file",
        ),
        "What format must the manuscript be submitted in?",
        "Which kind of file do I upload for the paper itself?",
    ),
    Fact(
        "cover_letter",
        "guideline",
        "Cover letter",
        "A cover letter is {v}.",
        ("mandatory", "optional", "only for resubmissions", "not accepted"),
        "Is a cover letter needed?",
        "Do I have to write a note to the editor when sending my paper?",
    ),
    Fact(
        "data_statement",
        "guideline",
        "Data availability",
        "A data availability statement is {v}.",
        (
            "mandatory",
            "encouraged but optional",
            "only for empirical studies",
            "not requested",
        ),
        "Is a data availability statement required?",
        "Must I say where my datasets can be found?",
    ),
    Fact(
        "word_limit",
        "guideline",
        "Length",
        "Research articles are limited to {v}.",
        ("5,000 words", "6,500 words", "8,000 words", "10,000 words"),
        "What is the word limit for research articles?",
        "How long can a full paper be?",
    ),
    Fact(
        "proofs",
        "guideline",
        "Proofs",
        "Authors must return proofs within {v}.",
        ("48 hours", "3 days", "5 days", "7 days"),
        "How quickly must proofs be returned?",
        "How much time do I have to check the typeset pages?",
    ),
    Fact(
        "ethics",
        "guideline",
        "Ethics",
        "An ethics approval statement is required {v}.",
        (
            "for studies with human participants",
            "for all submissions",
            "only for clinical trials",
            "only for animal research",
        ),
        "When is an ethics statement required?",
        "Do I need to mention committee clearance for my study?",
    ),
    Fact(
        "contributions",
        "guideline",
        "Authorship",
        "Author contributions are reported using {v}.",
        (
            "the CRediT taxonomy",
            "free-text statements",
            "a signed form",
            "initials after each section",
        ),
        "How are author contributions reported?",
        "Who did what: how do we state each person's role?",
    ),
)

# Knowledge that exists only as approved tickets (not in any document).
TICKET_TOPICS: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    (
        "special-issue embargo",
        "How long is the embargo for special issue papers?",
        "Papers in a special issue are embargoed for {v}.",
        ("6 months", "9 months", "12 months", "18 months"),
        "When may a special issue article be shared publicly?",
    ),
    (
        "reviewer reminders",
        "When do reviewers get a reminder?",
        "Reviewers receive a reminder {v}.",
        ("after 7 days", "after 14 days", "after 21 days", "after 28 days"),
        "How long before we nudge a referee who has not replied?",
    ),
    (
        "preprints",
        "Can authors post preprints?",
        "Authors may post preprints {v}.",
        (
            "on any server",
            "only on the journal's own server",
            "only after acceptance",
            "only as a private draft",
        ),
        "Is it allowed to put the paper online before it is accepted?",
    ),
)

UNAPPROVED = (
    "early-career waiver",
    "Is there a fee waiver for early-career authors?",
    "Early-career authors receive a 50% waiver.",
    "Do junior researchers get a discount on charges?",
)

UNANSWERABLE: tuple[str, ...] = (
    "What is the article processing charge?",
    "Who is the editor-in-chief?",
    "What is the journal's impact factor?",
    "Which indexing services list the journal?",
    "What is the acceptance rate?",
    "How do I reset my submission system password?",
    "What is the postal address of the editorial office?",
    "Does the journal offer print subscriptions?",
)

NOTE_SENTENCES = (
    "The production team reviewed how {t} are handled in recent issues and will revisit the topic next quarter.",
    "A reader asked a general question about {t}; the editorial office replied that it would be discussed.",
    "Minutes: {t} came up under any other business and no decision was recorded.",
    "Copyeditors reported that questions about {t} are common in the first week after acceptance.",
)

FILLER = (
    "Authors are encouraged to read this section carefully before submitting.",
    "Questions about this section can be sent to the editorial office.",
    "Editors may ask for changes that are not listed here.",
    "This guidance applies to all manuscript types unless stated otherwise.",
    "Consistent presentation helps readers and speeds up production.",
)

CHANGES_PER_JOURNAL = 6
DISTRACTORS_PER_JOURNAL = 12


@dataclass
class DocSpec:
    journal: str
    name: str
    kind: str  # DocumentKind value
    content_type: str
    versions: list[str]  # text of v1, v2, ...
    manuscript: str | None = None


@dataclass
class TicketSpec:
    journal: str
    key: str
    title: str
    answer: str
    approve: bool


@dataclass
class GoldenItem:
    id: str
    journal: str
    question: str
    type: ItemType
    style: Style = "na"
    manuscript: str | None = None
    evidence: str | None = None
    expect_abstain: bool = False
    expected_contains: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)


@dataclass
class Corpus:
    seed: int
    journals: list[str]
    manuscripts: dict[str, list[str]]
    docs: list[DocSpec]
    tickets: list[TicketSpec]
    golden: list[GoldenItem]

    def golden_jsonl(self) -> str:
        return (
            "\n".join(json.dumps(asdict(i), ensure_ascii=False) for i in self.golden)
            + "\n"
        )


def _section(heading: str, sentences: list[str], rng: random.Random) -> str:
    body = [*sentences, *rng.sample(FILLER, 2)]
    rng.shuffle(body)
    return f"# {heading}\n" + " ".join(body)


def _render(facts: list[Fact], values: dict[str, str], rng: random.Random) -> str:
    sections: dict[str, list[str]] = {}
    for fact in facts:
        sections.setdefault(fact.heading, []).append(
            fact.sentence.format(v=values[fact.key])
        )
    return "\n\n".join(_section(h, s, rng) for h, s in sections.items()) + "\n"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _forbidden(expected: str, candidates: list[str]) -> list[str]:
    """Values that must not appear, excluding any that overlap the expected one."""
    out: list[str] = []
    for c in candidates:
        if _norm(c) in _norm(expected) or _norm(expected) in _norm(c):
            continue
        if c not in out:
            out.append(c)
    return out


def build_corpus(seed: int = 7, n_journals: int = 3) -> Corpus:
    rng = random.Random(seed)
    journals = [f"J{chr(65 + i)}" for i in range(n_journals)]

    v1: dict[str, dict[str, str]] = {}
    v2: dict[str, dict[str, str]] = {}
    for j in journals:
        v1[j] = {f.key: rng.choice(f.values) for f in FACTS}
        v2[j] = dict(v1[j])
        for fact in rng.sample(FACTS, CHANGES_PER_JOURNAL):
            v2[j][fact.key] = rng.choice(
                [v for v in fact.values if v != v1[j][fact.key]]
            )

    docs: list[DocSpec] = []
    manuscripts: dict[str, list[str]] = {}
    golden: list[GoldenItem] = []
    tickets: list[TicketSpec] = []

    for j in journals:
        for kind, label, name in (
            ("stylesheet", "stylesheet", "House style.md"),
            ("guideline", "guideline", "Author guidelines.md"),
        ):
            facts = [f for f in FACTS if f.doc == label]
            texts = [
                _render(facts, values, random.Random(f"{seed}-{j}-{name}-{n}"))
                for n, values in enumerate((v1[j], v2[j]), 1)
            ]
            docs.append(DocSpec(j, name, kind, "text/markdown", texts))

        for n in range(DISTRACTORS_PER_JOURNAL):  # near-miss vocabulary, no rules
            topics = [f.heading.lower() for f in rng.sample(FACTS, 3)]
            note = " ".join(rng.choice(NOTE_SENTENCES).format(t=t) for t in topics)
            docs.append(
                DocSpec(
                    j,
                    f"Production note {n + 1}.md",
                    "other",
                    "text/markdown",
                    [f"# Production note {n + 1}\n{note}\n"],
                )
            )

        # Article-level exceptions: one as a note, one as an email.
        manuscripts[j] = [f"{j}-101", f"{j}-102"]
        exceptions = rng.sample(
            [
                f
                for f in FACTS
                if f.key in ("figure_dpi", "abstract", "word_limit", "title")
            ],
            2,
        )
        for index, (manuscript, fact) in enumerate(
            zip(manuscripts[j], exceptions, strict=True)
        ):
            current = v2[j][fact.key]
            special = rng.choice([v for v in fact.values if v != current])
            sentence = fact.sentence.format(v=special)
            if index == 0:
                text = f"# Editor note for {manuscript}\nFor manuscript {manuscript} the editor made an exception. {sentence}\n"
                docs.append(
                    DocSpec(
                        j,
                        f"{manuscript} editor note.md",
                        "manuscript",
                        "text/markdown",
                        [text],
                        manuscript,
                    )
                )
            else:
                text = (
                    f"From: editor@{j.lower()}.example\nTo: author@example.org\nSubject: Re: {manuscript} requirements\n\n"
                    f"Hello,\n\nFor manuscript {manuscript} we agreed an exception. {sentence}\n\nBest wishes\n"
                )
                docs.append(
                    DocSpec(
                        j,
                        f"{manuscript} editor email.eml",
                        "email_attachment",
                        "message/rfc822",
                        [text],
                        manuscript,
                    )
                )
            golden.append(
                GoldenItem(
                    f"{j}-art-{index}",
                    j,
                    fact.lexical,
                    "article",
                    "lexical",
                    manuscript,
                    sentence,
                    # Naming the general rule as context is fine; what matters is
                    # that the exception is stated and cited.
                    expected_contains=[special],
                )
            )
            golden.append(
                GoldenItem(
                    f"{j}-iso-{index}",
                    j,
                    fact.lexical,
                    "article_isolation",
                    "lexical",
                    None,
                    fact.sentence.format(v=current),
                    expected_contains=[current],
                    forbidden=_forbidden(current, [special]),
                )
            )

        for fact in FACTS:
            current, old = v2[j][fact.key], v1[j][fact.key]
            others = [v2[o][fact.key] for o in journals if o != j]
            stale = current != old
            forbidden = _forbidden(current, [*([old] if stale else []), *others])
            evidence = fact.sentence.format(v=current)
            for style, question in (
                ("lexical", fact.lexical),
                ("paraphrase", fact.paraphrase),
            ):
                golden.append(
                    GoldenItem(
                        f"{j}-{fact.key}-{style[:3]}",
                        j,
                        question,
                        "stale" if stale else "fact",
                        style,  # type: ignore[arg-type]
                        None,
                        evidence,
                        expected_contains=[current],
                        forbidden=forbidden,
                    )
                )

        for topic_index, (key, title, sentence, values, paraphrase) in enumerate(
            TICKET_TOPICS
        ):
            value = rng.choice(values)
            answer = sentence.format(v=value)
            tickets.append(TicketSpec(j, key, title, answer, approve=True))
            others = [other for other in values if other != value]
            for style, question in (("lexical", title), ("paraphrase", paraphrase)):
                golden.append(
                    GoldenItem(
                        f"{j}-tkt{topic_index}-{style[:3]}",
                        j,
                        question,
                        "ticket",
                        style,  # type: ignore[arg-type]
                        None,
                        answer,
                        expected_contains=[value],
                        forbidden=_forbidden(value, others),
                    )
                )

        key, title, answer, paraphrase = (
            UNAPPROVED[0],
            UNAPPROVED[1],
            UNAPPROVED[2],
            UNAPPROVED[3],
        )
        tickets.append(TicketSpec(j, key, title, answer, approve=False))
        for style, question in (("lexical", title), ("paraphrase", paraphrase)):
            golden.append(
                GoldenItem(
                    f"{j}-unapp-{style[:3]}",
                    j,
                    question,
                    "unapproved_trap",
                    style,  # type: ignore[arg-type]
                    None,
                    None,
                    expect_abstain=True,
                    forbidden=["50%"],
                )
            )

        for index, question in enumerate(UNANSWERABLE):
            golden.append(
                GoldenItem(
                    f"{j}-unans-{index}",
                    j,
                    question,
                    "unanswerable",
                    "na",
                    None,
                    None,
                    expect_abstain=True,
                )
            )

    return Corpus(seed, journals, manuscripts, docs, tickets, golden)
