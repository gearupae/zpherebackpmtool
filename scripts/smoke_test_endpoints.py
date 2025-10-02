from starlette.testclient import TestClient

# Ensure project root (parent of scripts/) is on sys.path
import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import the FastAPI app
try:
    from app.main import app
except Exception as e:
    print("Failed to import FastAPI app:", e)
    raise


def run_smoke_tests() -> int:
    """Run minimal health checks against the ASGI app without starting a server."""
    with TestClient(app) as client:
        def check(path: str, expected: set[int]) -> None:
            resp = client.get(path, follow_redirects=False)
            print(f"{path} -> {resp.status_code}")
            if resp.status_code not in expected:
                raise AssertionError(f"Unexpected status {resp.status_code} for {path}")

        # Basic health endpoints
        check("/health", {200})
        check("/api/v1/health", {200})
        # OpenAPI/Docs endpoints
        check("/api/v1/openapi.json", {200})
        check("/api/v1/docs", {200, 307, 308})

        print("SMOKE TESTS PASSED")
        return 0


if __name__ == "__main__":
    raise SystemExit(run_smoke_tests())

