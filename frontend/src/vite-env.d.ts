/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend base URL for split deploys (e.g. frontend on Vercel, backend on Render). Empty = same-origin. */
  readonly VITE_API_BASE?: string;
  /** Groq API key for the AI Operator Copilot (optional; the backend proxy is preferred). */
  readonly VITE_GROQ_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
