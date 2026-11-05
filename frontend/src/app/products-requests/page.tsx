import type { Metadata } from "next";

import { RouteBoundary } from "@/components/layout/route-boundary";
import { ProductsRequestsDashboard } from "@/features/analytics/products-requests-dashboard";

export const metadata: Metadata = { title: "Produits et demandes" };

export default function ProductsRequestsPage() {
  return (
    <RouteBoundary>
      <ProductsRequestsDashboard />
    </RouteBoundary>
  );
}
