import { LogOut } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import { PersonAvatar } from "./PersonAvatar"

export function UserMenu() {
  const { user, logout } = useAuth()
  if (!user) return <div className="size-9 rounded-full bg-muted" />
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account"
        className="rounded-full p-0.5 transition-shadow hover:shadow-e1 focus-visible:shadow-e1"
      >
        <PersonAvatar
          name={user.full_name}
          email={user.email}
          className="size-9 pointer-coarse:size-11 text-sm"
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72 rounded-2xl p-2">
        <DropdownMenuLabel className="flex flex-col items-center gap-2 px-4 py-5 font-normal">
          <PersonAvatar
            name={user.full_name}
            email={user.email}
            className="size-14 text-lg"
          />
          <div className="text-center">
            <p className="font-medium">{user.full_name ?? user.email}</p>
            <p className="text-sm text-muted-foreground">{user.email}</p>
          </div>
          {user.is_admin && <Badge variant="secondary">Administrator</Badge>}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => void logout()}
          className="gap-3 rounded-lg py-2.5"
        >
          <LogOut className="text-muted-foreground" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
