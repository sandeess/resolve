import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  CircleAlert,
  CloudUpload,
  Download,
  FileText,
  History,
  Loader2,
  type LucideIcon,
  Mail,
  RotateCw,
  Search,
} from "lucide-react"
import { useCallback, useRef, useState } from "react"

import {
  type DocumentKind,
  type DocumentPublic,
  DocumentsService,
  type DocumentVersionPublic,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { fullDate, timeAgo } from "@/lib/time"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

const KINDS: {
  value: DocumentKind
  label: string
  lead?: boolean
  hint: string
}[] = [
  {
    value: "stylesheet",
    label: "Stylesheet",
    lead: true,
    hint: "Formatting rules",
  },
  {
    value: "guideline",
    label: "Guideline",
    lead: true,
    hint: "Submission and author rules",
  },
  { value: "manuscript", label: "Manuscript", hint: "A paper or its notes" },
  { value: "email_attachment", label: "Email", hint: "A saved message" },
  { value: "other", label: "Other", hint: "Anything else" },
]
const KIND_LABEL = Object.fromEntries(
  KINDS.map((k) => [k.value, k.label]),
) as Record<DocumentKind, string>

function fileIcon(name: string): LucideIcon {
  return /\.(eml|msg)$/i.test(name) ? Mail : FileText
}

async function downloadVersion(version: DocumentVersionPublic, name: string) {
  const response = await DocumentsService.downloadVersion({
    path: { version_id: version.id },
    responseType: "blob",
  })
  const url = URL.createObjectURL(response.data as unknown as Blob)
  const link = document.createElement("a")
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

const STALE_PENDING_MS = 60_000

function isStalePending(version: DocumentVersionPublic): boolean {
  return (
    version.status === "pending" &&
    Date.now() - new Date(version.created_at).getTime() > STALE_PENDING_MS
  )
}

/** Whether a version can be found by Ask yet, with a retry when it is stuck or failed. */
function IndexState({
  version,
  compact,
}: {
  version: DocumentVersionPublic
  compact?: boolean
}) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const reindex = useMutation({
    mutationFn: () =>
      DocumentsService.reindexVersion({ path: { version_id: version.id } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
    onError: handleError.bind(showErrorToast),
  })
  const failed = version.status === "failed"
  const stuck = isStalePending(version)

  if (version.status === "indexed") {
    return (
      <span className="inline-flex h-6 items-center gap-1.5 rounded-full bg-success-soft px-2.5 text-xs font-medium text-success">
        <Search className="size-3" /> Searchable
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1">
      <span
        title={version.status_detail ?? undefined}
        className={cn(
          "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium",
          failed
            ? "bg-destructive/10 text-destructive"
            : "bg-warning-soft text-warning",
        )}
      >
        {failed ? (
          <CircleAlert className="size-3" />
        ) : (
          <Loader2 className="size-3 animate-spin" />
        )}
        {failed ? "Couldn't read this file" : "Getting ready..."}
      </span>
      {(failed || stuck) && !compact && (
        <Button
          variant="ghost"
          size="sm"
          disabled={reindex.isPending}
          onClick={() => reindex.mutate()}
        >
          <RotateCw /> Retry
        </Button>
      )}
    </span>
  )
}

function HistoryDrawer({
  document,
  onClose,
}: {
  document: DocumentPublic | null
  onClose: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["versions", document?.id],
    enabled: Boolean(document),
    queryFn: async () =>
      (
        await DocumentsService.listVersions({
          path: { document_id: (document as DocumentPublic).id },
        })
      ).data,
  })
  return (
    <Sheet open={Boolean(document)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full gap-0 sm:max-w-md">
        <SheetHeader className="border-b pb-4">
          <SheetTitle className="text-xl break-words">
            {document?.name}
          </SheetTitle>
          <SheetDescription>
            Every upload is kept. Only the latest version is used to answer
            questions.
          </SheetDescription>
        </SheetHeader>
        <ol className="flex flex-1 flex-col overflow-y-auto px-4 py-5">
          {isLoading && <Skeleton className="h-20 rounded-2xl" />}
          {data?.map((version, index) => (
            <li key={version.id} className="relative flex gap-4 pb-6 last:pb-0">
              {index < data.length - 1 && (
                <span className="absolute top-6 bottom-0 left-[11px] w-px bg-border" />
              )}
              <span
                className={cn(
                  "relative mt-1 size-6 shrink-0 rounded-full border-4 bg-card",
                  version.is_current ? "border-primary" : "border-border",
                )}
              />
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium">Version {version.version_no}</p>
                  {version.is_current && (
                    <span className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
                      Current
                    </span>
                  )}
                </div>
                <p
                  className="text-sm text-muted-foreground"
                  title={fullDate(version.created_at)}
                >
                  {timeAgo(version.created_at)} ·{" "}
                  {(version.size_bytes / 1024).toFixed(1)} KB
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <IndexState version={version} compact />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      document && void downloadVersion(version, document.name)
                    }
                  >
                    <Download /> Download
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </SheetContent>
    </Sheet>
  )
}

interface Props {
  journalId: string
  canUploadRules: boolean
  canUpload: boolean
}

/** Journal-level documents: drop files to upload, re-upload a name to add a version. */
const SUPPORTED = [".pdf", ".docx", ".txt", ".md", ".eml"]
const ACCEPT = SUPPORTED.join(",")
const isSupported = (file: File) =>
  SUPPORTED.some((ext) => file.name.toLowerCase().endsWith(ext))

export default function DocumentsPanel({
  journalId,
  canUploadRules,
  canUpload,
}: Props) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const input = useRef<HTMLInputElement>(null)
  const [kind, setKind] = useState<DocumentKind>(
    canUploadRules ? "stylesheet" : "other",
  )
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState<{
    done: number
    total: number
  } | null>(null)
  const [history, setHistory] = useState<DocumentPublic | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ["documents", journalId],
    queryFn: async () =>
      (
        await DocumentsService.listDocuments({
          path: { journal_id: journalId },
        })
      ).data,
    // Keep refreshing while the worker is still indexing something.
    refetchInterval: (query) =>
      query.state.data?.data.some(
        (d) => d.current_version?.status === "pending",
      )
        ? 2000
        : false,
  })

  const upload = useCallback(
    async (picked: File[]) => {
      const accepted = picked.filter((f) => isSupported(f))
      if (accepted.length < picked.length)
        showErrorToast(
          `Skipped ${picked.length - accepted.length} unsupported file(s). Use PDF, Word, Markdown, text or email.`,
        )
      const files = accepted
      if (files.length === 0) return
      let done = 0
      let succeeded = 0
      setProgress({ done, total: files.length })
      for (const file of files) {
        try {
          const { data: version } = await DocumentsService.uploadDocument({
            path: { journal_id: journalId },
            body: { file, kind },
          })
          succeeded += 1
          if (version.version_no > 1)
            showSuccessToast(
              `${file.name} saved as version ${version.version_no}`,
            )
        } catch (error) {
          handleError.call(showErrorToast, error as Error)
        }
        done += 1
        setProgress({ done, total: files.length })
      }
      setProgress(null)
      if (files.length > 1 && succeeded > 0)
        showSuccessToast(`${succeeded} files uploaded`)
      void queryClient.invalidateQueries({ queryKey: ["documents", journalId] })
      void queryClient.invalidateQueries({ queryKey: ["versions"] })
    },
    [journalId, kind, queryClient, showErrorToast, showSuccessToast],
  )

  const documents = data?.data ?? []
  const kinds = KINDS.filter((k) => !k.lead || canUploadRules)

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl sm:text-3xl">Documents</h1>
        <p className="text-muted-foreground">
          Stylesheets and guidelines Ask answers from. Upload a file with the
          same name to add a new version.
        </p>
      </header>

      {canUpload && (
        <section aria-label="Upload" className="flex flex-col gap-3">
          <div
            role="radiogroup"
            aria-label="Kind of file"
            className="flex flex-wrap gap-2"
          >
            {kinds.map((k) => (
              // biome-ignore lint/a11y/useSemanticElements: styled pill radio group
              <button
                key={k.value}
                type="button"
                role="radio"
                aria-checked={kind === k.value}
                title={k.hint}
                onClick={() => setKind(k.value)}
                className={cn(
                  "h-9 rounded-full border px-4 text-sm transition-colors",
                  kind === k.value
                    ? "border-transparent bg-secondary font-medium text-secondary-foreground"
                    : "hover:bg-accent",
                )}
              >
                {k.label}
              </button>
            ))}
          </div>
          {/* biome-ignore lint/a11y/noStaticElementInteractions: drop zone; a keyboard-accessible button inside picks files */}
          <div
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              void upload(Array.from(event.dataTransfer.files))
            }}
            className={cn(
              "flex flex-col items-center gap-3 rounded-3xl border-2 border-dashed px-6 py-10 text-center transition-colors",
              dragging
                ? "border-primary bg-secondary/60"
                : "border-border bg-muted/40",
            )}
          >
            <input
              ref={input}
              type="file"
              multiple
              accept={ACCEPT}
              hidden
              data-testid="document-file"
              onChange={(event) => {
                void upload(Array.from(event.target.files ?? []))
                event.target.value = ""
              }}
            />
            {progress ? (
              <>
                <Loader2 className="size-8 animate-spin text-primary" />
                <p className="font-medium">
                  Uploading {Math.min(progress.done + 1, progress.total)} of{" "}
                  {progress.total}...
                </p>
              </>
            ) : (
              <>
                <span className="flex size-14 items-center justify-center rounded-full bg-card text-primary shadow-e1">
                  <CloudUpload className="size-7" />
                </span>
                <div>
                  <p className="font-medium">
                    Drop files here to add them as{" "}
                    {KIND_LABEL[kind].toLowerCase()}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    PDF, Word, Markdown, text or email files
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => input.current?.click()}
                >
                  Browse files
                </Button>
              </>
            )}
          </div>
        </section>
      )}

      <section
        aria-label="Files"
        className="overflow-hidden rounded-2xl border"
      >
        {isLoading && (
          <div className="space-y-3 p-4">
            <Skeleton className="h-14 rounded-xl" />
            <Skeleton className="h-14 rounded-xl" />
          </div>
        )}
        {!isLoading && documents.length === 0 && (
          <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <FileText className="size-7" />
            </span>
            <h2 className="text-lg">No documents yet</h2>
            <p className="max-w-sm text-sm text-muted-foreground">
              {canUpload
                ? "Drop the journal's stylesheet above and Ask can start answering."
                : "Ask a lead to add the journal's stylesheet."}
            </p>
          </div>
        )}
        {documents.map((doc) => {
          const Icon = fileIcon(doc.name)
          const version = doc.current_version
          return (
            <div
              key={doc.id}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-4 py-3.5 transition-colors last:border-0 hover:bg-accent/50 sm:flex-nowrap"
            >
              <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
                <Icon className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{doc.name}</p>
                <p
                  className="truncate text-sm text-muted-foreground"
                  title={version ? fullDate(version.created_at) : undefined}
                >
                  {KIND_LABEL[doc.kind]}
                  {version &&
                    ` · version ${version.version_no} · ${timeAgo(version.created_at)}`}
                </p>
              </div>
              {version && <IndexState version={version} />}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setHistory(doc)}
                aria-label={`Version history of ${doc.name}`}
              >
                <History /> History
              </Button>
            </div>
          )
        })}
      </section>

      <HistoryDrawer document={history} onClose={() => setHistory(null)} />
    </div>
  )
}
