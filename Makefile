.PHONY: setup dev check e2e api-types

setup:      ## Install all dependencies from lockfiles
	./scripts/setup.sh
dev:        ## Run backend and frontend with hot reload
	./scripts/dev.sh
check:      ## Run every CI check except end-to-end tests
	./scripts/check.sh
e2e:        ## Run every check plus Playwright end-to-end tests
	./scripts/check.sh --e2e
api-types:  ## Regenerate OpenAPI schema + TypeScript types after changing backend schemas
	cd backend && uv run python scripts/export_openapi.py
	cd frontend && npm run gen:api
