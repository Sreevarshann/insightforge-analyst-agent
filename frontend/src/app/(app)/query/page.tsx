import type { Metadata } from "next";
import { QueryConsole } from "@/components/QueryConsole";

export const metadata: Metadata = { title: "Query Console" };

export default function Page() {
  return <QueryConsole />;
}
