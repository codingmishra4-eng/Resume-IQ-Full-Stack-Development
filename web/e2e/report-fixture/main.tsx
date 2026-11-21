// Browser-only test harness. This is not a Next.js route or production data source.
import { createRoot } from "react-dom/client";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "../../src/app/globals.css";
import { Analyzer } from "../../src/components/analyzer";
import { ToastProvider } from "../../src/components/ui";
import { AppShell } from "../../src/components/shell";
createRoot(document.getElementById("root")!).render(
  <ToastProvider>
    <AppShell>
      <Analyzer />
    </AppShell>
  </ToastProvider>,
);
