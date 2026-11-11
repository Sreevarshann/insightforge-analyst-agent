import type { Metadata } from "next";
import { Suspense } from "react";
import { DatasetExplorer } from "@/components/datasets/DatasetExplorer";
import { Skeleton } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Dataset Explorer" };

export default function DatasetsPage() {
  return (
    <Suspense fallback={<div className="p-6"><Skeleton className="h-10 w-64" /></div>}>
      <DatasetExplorer />
    </Suspense>
  );
}
