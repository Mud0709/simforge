import type { components } from "./schema";

type Schemas = components["schemas"];
export type ProjectileParameters = Schemas["ProjectileParameters"];
export type SolverSettings = Schemas["SolverSettings"];
export type ProjectileRequest = Schemas["ProjectileRequest"];
export type ProjectileResponse = Schemas["ProjectileResponse"];
export type ExperimentRecord = Schemas["ExperimentRecord"];
export type ErrorMetric = Schemas["ErrorMetric"];
export type AngleSweepRequest = Schemas["AngleSweepRequest"];
export type AngleSweepResponse = Schemas["AngleSweepResponse"];
export type IntegratorStudyRequest = Schemas["IntegratorStudyRequest"];
export type IntegratorStudyResponse = Schemas["IntegratorStudyResponse"];
export type MethodStudyResult = Schemas["MethodStudyResult"];
export type IntegratorMethod = MethodStudyResult["method"];
export type SolowParameters = Schemas["SolowParameters"];
export type SavingsPolicy = Schemas["SavingsPolicy"];
export type SolowRequest = Schemas["SolowRequest"];
export type SolowResponse = Schemas["SolowResponse"];
export type SolowPath = Schemas["SolowPathResponse"];
export type ValidationCheck = Schemas["ValidationCheck"];
export type ProfileRequest = Schemas["ProfileRequest"];
export type ProfileResponse = Schemas["ProfileResponse"];
export type ParseOptions = Schemas["ParseOptions"];
export type ColumnProfile = Schemas["ColumnProfile"];
export type ColumnType = Schemas["ColumnOverride"]["type"];
export type Delimiter = NonNullable<ParseOptions["delimiter"]>;
export type SampleInfo = Schemas["SampleInfo"];
export type SampleId = SampleInfo["id"];

const API_BASE = "/api/v1";

/** An error returned by the API, with a human-readable message extracted from FastAPI's body. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type FastApiDetail = string | { loc?: (string | number)[]; msg?: string }[];

export function describeError(detail: FastApiDetail | undefined, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d) => {
        // Drop the "body" prefix FastAPI adds; keep the field path the user recognises.
        const field = (d.loc ?? []).filter((p) => p !== "body").join(".");
        const msg = (d.msg ?? "invalid value").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join("; ");
  }
  return `Request failed with status ${status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Could not reach the SimForge API. Is the backend running on :8000?");
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: FastApiDetail };
    throw new ApiError(res.status, describeError(body.detail, res.status));
  }
  return (await res.json()) as T;
}

export function simulateProjectile(body: ProjectileRequest): Promise<ProjectileResponse> {
  return request("/physics/projectile/simulate", { method: "POST", body: JSON.stringify(body) });
}

export function runAngleSweep(body: AngleSweepRequest): Promise<AngleSweepResponse> {
  return request("/physics/projectile/angle-sweep", { method: "POST", body: JSON.stringify(body) });
}

export function runIntegratorStudy(body: IntegratorStudyRequest): Promise<IntegratorStudyResponse> {
  return request("/physics/projectile/integrators", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function simulateSolow(body: SolowRequest): Promise<SolowResponse> {
  return request("/economy/solow/simulate", { method: "POST", body: JSON.stringify(body) });
}

export function listSampleDatasets(): Promise<SampleInfo[]> {
  return request("/quant/datasets/samples");
}

export function profileDataset(body: ProfileRequest): Promise<ProfileResponse> {
  return request("/quant/datasets/profile", { method: "POST", body: JSON.stringify(body) });
}

export function listExperiments(limit = 50): Promise<ExperimentRecord[]> {
  return request(`/experiments?limit=${limit}`);
}
