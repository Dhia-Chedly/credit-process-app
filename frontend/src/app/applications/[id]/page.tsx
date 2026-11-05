import type { Metadata } from "next";

import { ApplicationDetail } from "@/features/applications/application-detail";

export const metadata: Metadata = { title: "Détail de la demande" };

export default async function ApplicationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ApplicationDetail applicationId={id} />;
}
