import type { Metadata } from "next";
import { Suspense } from "react";
import { Workspace } from "@/components/workspace/Workspace";
import { Skeleton } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Analysis Copilot" };

export default function WorkspacePage() {
  return (
    <Suspense fallback={<div className="p-6"><Skeleton className="h-10 w-80" /></div>}>
      <Workspace />
    </Suspense>
  );
}
