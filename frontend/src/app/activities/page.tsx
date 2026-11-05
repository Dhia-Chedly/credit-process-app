import type { Metadata } from "next";

import { RouteBoundary } from "@/components/layout/route-boundary";
import { ActivityDashboard } from "@/features/analytics/activity-dashboard";

export const metadata: Metadata = { title: "Activités financées" };

export default function ActivitiesPage() {
  return (
    <RouteBoundary>
      <ActivityDashboard />
    </RouteBoundary>
  );
}
