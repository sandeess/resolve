import { UserManager, WebStorageStateStore } from "oidc-client-ts"

/**
 * Single OIDC client for the app (authorization-code flow with PKCE).
 * Tokens live in sessionStorage so they die with the tab.
 */
export const userManager = new UserManager({
  authority: import.meta.env.VITE_OIDC_AUTHORITY,
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID,
  redirect_uri: window.location.origin,
  post_logout_redirect_uri: window.location.origin,
  scope: "openid profile email",
  response_type: "code",
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  // The 15-minute access token is refreshed by re-running the code flow, which
  // is seamless while the identity provider session is alive (see main.tsx).
  automaticSilentRenew: false,
})

export async function getAccessToken(): Promise<string> {
  const user = await userManager.getUser()
  return user && !user.expired ? user.access_token : ""
}
