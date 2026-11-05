import { RouteBoundary } from "@/components/layout/route-boundary";
import { ExecutiveOverview } from "@/features/analytics/executive-overview";

export default function HomePage() {
  return (
    <RouteBoundary>
      <ExecutiveOverview />
    </RouteBoundary>
  );
}
