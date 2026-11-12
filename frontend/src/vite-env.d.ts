/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin, e.g. https://evidra-api.onrender.com. Unset in local dev (relative /api). */
  readonly VITE_API_BASE_URL?: string;
  /** "true" enables password-less guest sign-in for the public demo. */
  readonly VITE_DEMO_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
