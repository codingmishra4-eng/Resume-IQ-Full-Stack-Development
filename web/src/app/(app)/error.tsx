"use client";
import { Button, EmptyState } from "@/components/ui";
export default function ErrorBoundary({ reset }: { reset: () => void }) {
  return (
    <EmptyState
      title="Let’s try that again."
      action={<Button onClick={reset}>Reload this page</Button>}
    >
      This page could not be loaded. Your stored documents have not been
      changed.
    </EmptyState>
  );
}
