import { describe, expect, it } from "vitest";
import { traceSummary } from "./trace";
import type { TraceStep } from "../types/report";

const step = (
  actor: TraceStep["actor"],
  status: TraceStep["status"] = "ok",
): TraceStep => ({
  actor,
  name: actor,
  detail: "",
  status,
  duration_ms: 1,
  claim_ids: [],
});

describe("traceSummary", () => {
  it("counts tools, model calls and validator rejections", () => {
    const trace = [
      step("planner"),
      step("tool"),
      step("tool"),
      step("validator", "rejected"),
    ];
    expect(traceSummary(trace, 1, 2400)).toBe(
      "2 tool calls · 1 model call · 1 rejected by the validator · 2.4s",
    );
  });
  it("omits rejections when there are none", () => {
    expect(traceSummary([step("tool")], 0, 500)).toBe(
      "1 tool call · 0 model calls · 0.5s",
    );
  });
});
