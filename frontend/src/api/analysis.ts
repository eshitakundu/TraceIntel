import type { Chain, Job, Report } from "../types/report";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch("/api/v1" + path, options);
  if (!response.ok) {
    let message = "The API could not complete this request.";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* Keep safe fallback for proxy errors. */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export const getChains = (signal?: AbortSignal) =>
  request<Chain[]>("/chains", { signal });
export const submitAnalysis = (chain: string, transaction_hash: string) =>
  request<Job>("/analyses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chain, transaction_hash }),
  });
export const getJob = (id: string, signal?: AbortSignal) =>
  request<Job>("/analyses/" + encodeURIComponent(id), { signal });
export const getReport = (id: string, signal?: AbortSignal) =>
  request<Report>("/reports/" + encodeURIComponent(id), { signal });
