import type { Metadata } from "next";
import { SavedAnalyses } from "@/components/SavedAnalyses";

export const metadata: Metadata = { title: "Saved Analyses" };

export default function Page() {
  return <SavedAnalyses />;
}
