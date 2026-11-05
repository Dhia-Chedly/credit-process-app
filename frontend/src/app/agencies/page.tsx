import type { Metadata } from "next";

import { RouteBoundary } from "@/components/layout/route-boundary";
import { AgencyDashboard } from "@/features/analytics/agency-dashboard";

export const metadata: Metadata = { title: "Réseau" };

export default function AgenciesPage() {
  return (
    <RouteBoundary>
      <AgencyDashboard />
    </RouteBoundary>
  );
}
