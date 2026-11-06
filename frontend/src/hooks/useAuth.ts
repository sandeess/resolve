import { useQuery } from "@tanstack/react-query"
import { useAuth as useOidc } from "react-oidc-context"

import { MeService, type UserPublic } from "@/client"

/** Signed-in user (from our API, not just token claims) plus login/logout. */
export default function useAuth() {
  const oidc = useOidc()

  const { data: user } = useQuery<UserPublic>({
    queryKey: ["me"],
    queryFn: async () => (await MeService.readMe()).data,
    enabled: oidc.isAuthenticated,
  })

  return {
    user,
    isAuthenticated: oidc.isAuthenticated,
    isLoading: oidc.isLoading,
    error: oidc.error,
    login: () => oidc.signinRedirect(),
    logout: () => oidc.signoutRedirect(),
  }
}
