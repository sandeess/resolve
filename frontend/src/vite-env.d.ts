/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  /** Google Form (or any page) where new people ask for an account. */
  readonly VITE_ACCESS_REQUEST_URL?: string
  /** Where "Request access" emails go when there is no form. */
  readonly VITE_ACCESS_REQUEST_EMAIL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
