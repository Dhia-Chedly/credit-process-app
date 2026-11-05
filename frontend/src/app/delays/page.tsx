import type { Metadata } from "next";

import { RouteBoundary } from "@/components/layout/route-boundary";
import { DelayDashboard } from "@/features/analytics/delay-dashboard";

export const metadata: Metadata = { title: "Flux & délais" };

export default function DelaysPage() {
  return (
    <RouteBoundary>
      <DelayDashboard />
    </RouteBoundary>
  );
}
