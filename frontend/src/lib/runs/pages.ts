/** The page that shows each model, so a saved run can be reopened where it was made. */
const PAGES: Record<string, string> = {
  "physics.projectile": "/physics/projectile",
  // A sweep starts from the projectile page's parameters.
  "physics.projectile.angle_sweep": "/physics/projectile",
  "physics.projectile.integrators": "/physics/projectile/integrators",
  "economy.solow": "/economy/solow",
  "quant.dataset_profile": "/quant/datasets",
};

/** Link that reopens a run on its page, or null for a model SimForge no longer has. */
export function reopenLink(modelId: string, runId: string): string | null {
  const page = PAGES[modelId];
  return page ? `${page}?run=${encodeURIComponent(runId)}` : null;
}
