import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StageProgress } from "@/components/workspace/StageProgress";
import { VerificationBadge } from "@/components/workspace/VerificationBadge";

describe("VerificationBadge", () => {
  it("shows the number of removed sentences when corrected", () => {
    render(<VerificationBadge v={{ status: "corrected", removed_sentences: [{ sentence: "x", reason: "y" }, { sentence: "a", reason: "b" }] }} />);
    expect(screen.getByText(/corrected · 2 removed/)).toBeInTheDocument();
  });
  it("labels abstentions as facts-only", () => {
    render(<VerificationBadge v={{ status: "abstained" }} />);
    expect(screen.getByText(/facts only/)).toBeInTheDocument();
  });
});

describe("StageProgress", () => {
  it("only marks stages the server has reported", () => {
    render(<StageProgress stages={{ catalog: { status: "done", ms: 5 }, plan: { status: "start", attempt: 2 } }} />);
    expect(screen.getByText("Read catalog").parentElement).toHaveTextContent("complete");
    expect(screen.getByText("Plan").parentElement).toHaveTextContent("running");
    expect(screen.getByText("#2")).toBeInTheDocument();
    expect(screen.getByText("Execute").parentElement).toHaveTextContent("pending");
  });
});
