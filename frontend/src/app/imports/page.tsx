import type { Metadata } from "next";

import { ImportsDashboard } from "@/features/imports/imports-dashboard";

export const metadata: Metadata = { title: "Imports and data quality" };

export default function ImportsPage() {
  return <ImportsDashboard />;
}
