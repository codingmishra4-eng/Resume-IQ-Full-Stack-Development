import type { NextConfig } from "next";
import { assertPublicEnvironment } from "./public-env.mjs";
assertPublicEnvironment(process.env);
const config: NextConfig = {
  poweredByHeader: false,
  logging: false, // Callback URLs may contain one-time codes; do not log incoming URLs.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          { key: "Cache-Control", value: "private, no-store" },
        ],
      },
    ];
  },
};
export default config;
