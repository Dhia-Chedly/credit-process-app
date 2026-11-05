import { Suspense, type ReactNode } from "react";

import { LoadingState } from "@/components/ui/data-state";

export function RouteBoundary({ children }: { children: ReactNode }) {
  return <Suspense fallback={<LoadingState />}>{children}</Suspense>;
}
