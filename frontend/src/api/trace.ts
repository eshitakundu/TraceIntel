import type { TraceStep } from "../types/report";

/** One-line account of an agent run: tools, model calls, rejections, time. */
export function traceSummary(trace: TraceStep[], llmCalls = 0, ms = 0) {
  const tools = trace.filter((step) => step.actor === "tool").length;
  const rejected = trace.filter((step) => step.status === "rejected").length;
  return [
    tools + (tools === 1 ? " tool call" : " tool calls"),
    llmCalls + (llmCalls === 1 ? " model call" : " model calls"),
    rejected ? rejected + " rejected by the validator" : null,
    (ms / 1000).toFixed(1) + "s",
  ]
    .filter(Boolean)
    .join(" · ");
}
