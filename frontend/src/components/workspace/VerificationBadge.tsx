import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import type { Verification } from "@/lib/types";
import { Badge } from "../ui/primitives";

export function VerificationBadge({ v }: { v: Verification | null | undefined }) {
  if (!v) return null;
  if (v.status === "verified") return <Badge tone="lime" title="Every number in the explanation was checked against computed facts"><ShieldCheck className="size-3" /> verified</Badge>;
  if (v.status === "corrected") return <Badge tone="warn" title="Unverifiable sentences were removed"><ShieldAlert className="size-3" /> corrected · {v.removed_sentences?.length ?? 0} removed</Badge>;
  return <Badge tone="coral" title="The model's draft could not be verified; showing computed facts instead"><ShieldQuestion className="size-3" /> abstained · facts only</Badge>;
}
