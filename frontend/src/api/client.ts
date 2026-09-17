export interface Health {
  status: "ok";
  service: "traceintel-api";
  version: string;
}

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch("/api/v1/ready", { signal, cache: "no-store" });
  if (!response.ok)
    throw new Error(
      "The API is unavailable. Check that the backend is running.",
    );
  const data: unknown = await response.json();
  if (
    !data ||
    typeof data !== "object" ||
    !("status" in data) ||
    data.status !== "ok" ||
    !("service" in data) ||
    data.service !== "traceintel-api" ||
    !("version" in data) ||
    typeof data.version !== "string"
  ) {
    throw new Error("The API returned an unexpected health response.");
  }
  return data as Health;
}
