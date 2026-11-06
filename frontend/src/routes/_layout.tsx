import { createFileRoute, Outlet } from "@tanstack/react-router"
import { useAuth } from "react-oidc-context"

import { Landing } from "@/components/Landing/Landing"
import { AppShell } from "@/components/Shell/AppShell"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_layout")({
  component: Layout,
})

function FullPageMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-muted-foreground">
      {children}
    </div>
  )
}

/** Signed-in users get the app; everyone else gets the front page. */
function RequireSignIn({ children }: { children: React.ReactNode }) {
  const auth = useAuth()
  const signIn = () => {
    const returnTo = window.location.pathname + window.location.search
    void auth.signinRedirect({ state: returnTo })
  }

  if (auth.error) {
    return (
      <FullPageMessage>
        <p>Sign-in failed: {auth.error.message}</p>
        <Button onClick={signIn}>Try again</Button>
      </FullPageMessage>
    )
  }
  if (auth.isLoading || auth.activeNavigator) {
    return <FullPageMessage>Signing you in…</FullPageMessage>
  }
  if (!auth.isAuthenticated) {
    return <Landing onSignIn={signIn} />
  }
  return <>{children}</>
}

function Layout() {
  return (
    <RequireSignIn>
      <AppShell>
        <Outlet />
      </AppShell>
    </RequireSignIn>
  )
}
