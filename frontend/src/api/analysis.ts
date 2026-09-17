import type { Chain, Job, Report } from "../types/report";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function isTemporaryApiError(error: unknown): boolean {
  return error instanceof ApiError && [0, 502, 503, 504].includes(error.status);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 35000);
  const signal = options?.signal
    ? AbortSignal.any([options.signal, controller.signal])
    : controller.signal;
  try {
    const response = await fetch("/api/v1" + path, {
      ...options,
      signal,
      cache: "no-store",
    });
    if (!response.ok) {
      let message = "The API could not complete this request.";
      try {
        const body = await response.json();
        if (typeof body.detail === "string") message = body.detail;
      } catch {
        /* Preserve status when a gateway returns HTML. */
      }
      throw new ApiError(message, response.status);
    }
    try {
      return (await response.json()) as T;
    } catch {
      throw new ApiError("The API returned an unreadable response.", 502);
    }
  } catch (error) {
    if (error instanceof ApiError || options?.signal?.aborted) throw error;
    throw new ApiError(
      controller.signal.aborted
        ? "The API request timed out."
        : "The API connection was interrupted.",
      0,
    );
  } finally {
    clearTimeout(timeout);
  }
}
export const getChains = (signal?: AbortSignal) =>
  request<Chain[]>("/chains", { signal });
export const submitAnalysis = (
  chain: string,
  transaction_hash: string,
  signal?: AbortSignal,
) =>
  request<Job>("/analyses", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chain, transaction_hash }),
  });
export const getJob = (id: string, signal?: AbortSignal) =>
  request<Job>("/analyses/" + encodeURIComponent(id), { signal });
export const getReport = (id: string, signal?: AbortSignal) =>
  request<Report>("/reports/" + encodeURIComponent(id), { signal });
