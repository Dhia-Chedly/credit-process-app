"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { DataState } from "@/components/ui/data-state";

export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <DataState title="This dashboard view could not be rendered" tone="error">
      <p>No data was changed. Retry the view, or verify that the analytics API is available.</p>
      <Button className="mt-4" onClick={reset} variant="secondary">
        Retry
      </Button>
    </DataState>
  );
}
