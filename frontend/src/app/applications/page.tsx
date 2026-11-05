import type { Metadata } from "next";

import { ApplicationsDashboard } from "@/features/applications/applications-dashboard";

export const metadata: Metadata = { title: "Applications" };

export default function ApplicationsPage() {
  return <ApplicationsDashboard />;
}
