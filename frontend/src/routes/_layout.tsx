import { createFileRoute, Outlet } from "@tanstack/react-router"
import { useEffect } from "react"
import { useAuth } from "react-oidc-context"

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

/** Renders children only for signed-in users; otherwise starts the OIDC flow. */
function RequireSignIn({ children }: { children: React.ReactNode }) {
  const auth = useAuth()
  const shouldRedirect =
    !auth.isLoading &&
    !auth.isAuthenticated &&
    !auth.activeNavigator &&
    !auth.error

  useEffect(() => {
    if (shouldRedirect) {
      const returnTo = window.location.pathname + window.location.search
      void auth.signinRedirect({ state: returnTo })
    }
  }, [shouldRedirect, auth])

  if (auth.error) {
    return (
      <FullPageMessage>
        <p>Sign-in failed: {auth.error.message}</p>
        <Button onClick={() => void auth.signinRedirect()}>Try again</Button>
      </FullPageMessage>
    )
  }
  if (!auth.isAuthenticated) {
    return <FullPageMessage>Signing you in…</FullPageMessage>
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
