"""Domain errors raised by scientific code and translated to HTTP responses by the API layer."""


class ModelDomainError(ValueError):
    """Inputs are individually valid, but the requested run is outside what the model or
    solver can handle reliably (e.g. a stiff problem sent to an explicit solver)."""


class SolverError(RuntimeError):
    """The numerical solver failed or did not reach the expected terminating event."""
