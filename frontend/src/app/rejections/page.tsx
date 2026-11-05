import type { Metadata } from "next";

import { RouteBoundary } from "@/components/layout/route-boundary";
import { RejectionDashboard } from "@/features/analytics/rejection-dashboard";

export const metadata: Metadata = { title: "Rejets" };

export default function RejectionsPage() {
  return (
    <RouteBoundary>
      <RejectionDashboard />
    </RouteBoundary>
  );
}
