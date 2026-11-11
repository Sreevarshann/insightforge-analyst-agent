import type { Metadata } from "next";
import { Evaluation } from "@/components/Evaluation";

export const metadata: Metadata = { title: "Evaluation" };

export default function Page() {
  return <Evaluation />;
}
