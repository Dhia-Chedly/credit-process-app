import type { Metadata } from "next";

import { ImportDetail } from "@/features/imports/import-detail";

export const metadata: Metadata = { title: "Import quality report" };

export default async function ImportDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ImportDetail importId={id} />;
}
