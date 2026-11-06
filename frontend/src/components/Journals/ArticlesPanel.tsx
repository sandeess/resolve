import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { BookOpen, Plus, Search } from "lucide-react"
import { useState } from "react"

import { JournalsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface Props {
  journalId: string
  canCreate: boolean
}

/** Articles (manuscripts) registered under a journal. Ask can be narrowed to one. */
export default function ArticlesPanel({ journalId, canCreate }: Props) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [adding, setAdding] = useState(false)
  const [manuscriptId, setManuscriptId] = useState("")
  const [title, setTitle] = useState("")

  const { data, isLoading } = useQuery({
    queryKey: ["articles", journalId],
    queryFn: async () =>
      (await JournalsService.listArticles({ path: { journal_id: journalId } }))
        .data,
  })

  const create = useMutation({
    mutationFn: () =>
      JournalsService.createArticle({
        path: { journal_id: journalId },
        body: { manuscript_id: manuscriptId.trim(), title: title.trim() },
      }),
    onSuccess: () => {
      showSuccessToast("Article added")
      setManuscriptId("")
      setTitle("")
      setAdding(false)
      void queryClient.invalidateQueries({ queryKey: ["articles", journalId] })
    },
    onError: handleError.bind(showErrorToast),
  })
  const valid = manuscriptId.trim().length > 0 && title.trim().length > 0
  const articles = data ?? []

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl">Articles</h1>
          <p className="text-muted-foreground">
            Manuscripts in this journal. Ask can focus on one of them.
          </p>
        </div>
        {canCreate && (
          <Button onClick={() => setAdding(true)}>
            <Plus /> Add article
          </Button>
        )}
      </header>

      <div className="overflow-hidden rounded-2xl border">
        {isLoading && (
          <div className="space-y-3 p-4">
            <Skeleton className="h-12 rounded-xl" />
            <Skeleton className="h-12 rounded-xl" />
          </div>
        )}
        {!isLoading && articles.length === 0 && (
          <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <BookOpen className="size-7" />
            </span>
            <h2 className="text-lg">No articles yet</h2>
            <p className="max-w-sm text-sm text-muted-foreground">
              Add a manuscript to keep its own notes and emails, and to ask
              questions about it specifically.
            </p>
          </div>
        )}
        {articles.map((article) => (
          <div
            key={article.id}
            className="flex items-center gap-4 border-b px-4 py-3.5 last:border-0 hover:bg-accent/50"
          >
            <span className="flex h-10 min-w-16 items-center justify-center rounded-xl bg-secondary px-3 text-xs font-semibold text-secondary-foreground">
              {article.manuscript_id}
            </span>
            <p className="min-w-0 flex-1 truncate font-medium">
              {article.title}
            </p>
            <Button asChild variant="ghost" size="sm">
              <Link
                to="/journals/$journalId/ask"
                params={{ journalId }}
                search={{ a: article.id }}
              >
                <Search /> Ask about it
              </Link>
            </Button>
          </div>
        ))}
      </div>

      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent>
          <form
            className="grid gap-5"
            onSubmit={(event) => {
              event.preventDefault()
              if (valid) create.mutate()
            }}
          >
            <DialogHeader>
              <DialogTitle className="text-xl">Add an article</DialogTitle>
              <DialogDescription>
                Register a manuscript so it can have its own documents.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-2">
              <Label htmlFor="manuscript-id">Manuscript ID</Label>
              <Input
                id="manuscript-id"
                autoFocus
                value={manuscriptId}
                onChange={(e) => setManuscriptId(e.target.value)}
                placeholder="e.g. JNL-101"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="article-title">Title</Label>
              <Input
                id="article-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setAdding(false)}
              >
                Cancel
              </Button>
              <LoadingButton
                type="submit"
                loading={create.isPending}
                disabled={!valid}
              >
                Add article
              </LoadingButton>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
