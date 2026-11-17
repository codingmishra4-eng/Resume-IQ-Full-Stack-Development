import type { Metadata } from "next";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "ResumeIQ — Your experience, clearly told.",
    template: "%s · ResumeIQ",
  },
  description:
    "A private workspace for your resumes, job applications and professional story.",
  robots: { index: false, follow: false },
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
