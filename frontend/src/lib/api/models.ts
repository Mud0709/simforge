import type {
  AngleSweepResponse,
  IntegratorStudyResponse,
  ModelResponse,
  ProfileResponse,
  ProjectileResponse,
  SolowResponse,
} from "./client";

/** Each model id and the response it returns. */
export interface ResponseOf {
  "physics.projectile": ProjectileResponse;
  "physics.projectile.angle_sweep": AngleSweepResponse;
  "physics.projectile.integrators": IntegratorStudyResponse;
  "economy.solow": SolowResponse;
  "quant.dataset_profile": ProfileResponse;
}

export type ModelId = keyof ResponseOf;

/**
 * Narrows a response to one model by its `model.id`. The OpenAPI union has no discriminator
 * mapping (the server tells the responses apart by `model.id` too), so TypeScript cannot
 * narrow it on its own.
 */
export function isModelResponse<K extends ModelId>(
  response: ModelResponse,
  id: K,
): response is ResponseOf[K] {
  return response.model.id === id;
}
