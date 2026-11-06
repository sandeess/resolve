import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { AxiosError } from "axios"
import type { User } from "oidc-client-ts"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { AuthProvider } from "react-oidc-context"
import { getAccessToken, userManager } from "./auth/oidc"
import { client } from "./client/client.gen"
import { ThemeProvider } from "./components/theme-provider"
import { Toaster } from "./components/ui/sonner"
import "./index.css"
import { routeTree } from "./routeTree.gen"

client.setConfig({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  auth: getAccessToken,
})

// An expired or rejected token means "sign in again"; the identity provider
// session usually makes that instant. 403 is a real permission error: leave it
// to the caller so users see why an action failed.
const handleApiError = (error: Error) => {
  if (error instanceof AxiosError && error.response?.status === 401) {
    void userManager.removeUser().then(() => userManager.signinRedirect())
  }
}
const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleApiError }),
  mutationCache: new MutationCache({ onError: handleApiError }),
})

const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

// After the code exchange, drop ?code=&state= and return to the page the user
// was on when sign-in started (carried through the flow as `state`).
const onSigninCallback = (user: User | undefined) => {
  const target = typeof user?.state === "string" ? user.state : "/"
  router.history.replace(target)
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
      <AuthProvider
        userManager={userManager}
        onSigninCallback={onSigninCallback}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
          <Toaster position="bottom-left" />
        </QueryClientProvider>
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
)
