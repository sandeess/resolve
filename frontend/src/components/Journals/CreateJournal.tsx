import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
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
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

/** Administrator-only dialog that creates a journal. */
export default function CreateJournal() {
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState("")
  const [name, setName] = useState("")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => JournalsService.createJournal({ body: { code, name } }),
    onSuccess: () => {
      showSuccessToast("Journal created")
      setOpen(false)
      setCode("")
      setName("")
      void queryClient.invalidateQueries({ queryKey: ["journals"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const valid = code.length >= 2 && name.trim().length > 0

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> New journal
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form
          className="grid gap-5"
          onSubmit={(event) => {
            event.preventDefault()
            if (valid) mutation.mutate()
          }}
        >
          <DialogHeader>
            <DialogTitle className="text-xl">New journal</DialogTitle>
            <DialogDescription>
              Each journal keeps its own stylesheets, articles and tickets.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="journal-code">Code</Label>
            <Input
              id="journal-code"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="JNL"
              maxLength={12}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="journal-name">Name</Label>
            <Input
              id="journal-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Journal of Examples"
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <LoadingButton
              type="submit"
              loading={mutation.isPending}
              disabled={!valid}
            >
              Create journal
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
