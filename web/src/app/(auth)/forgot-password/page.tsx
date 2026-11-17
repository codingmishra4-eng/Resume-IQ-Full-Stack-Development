import { Suspense } from "react";
import { AuthForm } from "@/components/auth-form";
import { Skeleton } from "@/components/ui";
export default function Page() {
  return (
    <Suspense fallback={<Skeleton />}>
      <AuthForm mode="forgot" />
    </Suspense>
  );
}
