// Only adds a safety check; everything else is Vite's default behaviour.
import { loadEnv } from "vite";

// A production build that still points at the developer's own computer would "work" for the
// developer and show a broken site to everyone else. Refuse to build it by accident.
// Override on purpose (e.g. a local preview build):  ALLOW_LOCAL_API=1 npm run build
function requirePublicApiUrl() {
  return {
    name: "require-public-api-url",
    config(_, { mode, command }) {
      if (command !== "build" || mode !== "production" || process.env.ALLOW_LOCAL_API === "1") return;
      const url = loadEnv(mode, process.cwd(), "VITE_").VITE_API_BASE_URL || process.env.VITE_API_BASE_URL || "";
      if (!/^https:\/\/[^/]+/i.test(url) || /localhost|127\.0\.0\.1|0\.0\.0\.0/.test(url)) {
        throw new Error(
          "\n\nVITE_API_BASE_URL must be the public HTTPS address of your backend, e.g.\n" +
          "  https://your-backend.example.com/api\n" +
          `Currently: ${url || "(not set)"}\n` +
          "Set it before building (PowerShell:  $env:VITE_API_BASE_URL=\"https://.../api\"; npm run build),\n" +
          "or build a local-only preview with:  ALLOW_LOCAL_API=1 npm run build\n"
        );
      }
    },
  };
}

export default { plugins: [requirePublicApiUrl()] };
