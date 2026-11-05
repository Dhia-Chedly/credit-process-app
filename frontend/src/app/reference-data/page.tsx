import type { Metadata } from "next";

import { ReferenceDataDashboard } from "@/features/reference-data/reference-data-dashboard";

export const metadata: Metadata = { title: "Référentiels opérationnels" };

export default function ReferenceDataPage() {
  return <ReferenceDataDashboard />;
}
