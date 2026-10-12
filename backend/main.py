from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.health import router as health_router
from api.auth import router as auth_router
from api.research_harness import router as research_harness_router
from config.db import SessionLocal
from config.settings import settings
from services.security.audit import write_audit_log
from services.security.auth import authenticate_token, extract_api_token
from services.security.rate_limit import consume_rate_limit

app = FastAPI(title="ScholarFlow API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
    request.state.request_id = request_id
    start = perf_counter()
    response = None
    is_cors_preflight = (
        request.method.upper() == "OPTIONS"
        and bool(request.headers.get("Origin"))
        and bool(request.headers.get("Access-Control-Request-Method"))
    )
    token = None if is_cors_preflight else extract_api_token(request.headers.get("Authorization"))
    identity = None if is_cors_preflight else authenticate_token(token)
    request.state.identity = identity
    should_protect = request.url.path.startswith("/api")
    public_api_paths = {"/api/auth/session", "/api/auth/config"}
    is_public_auth_route = request.url.path in public_api_paths

    try:
        if is_cors_preflight:
            response = await call_next(request)
        elif should_protect and not is_public_auth_route and (settings.api_token or settings.auth_required) and identity is None:
            response = JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        elif should_protect:
            client_ip = request.client.host if request.client else "unknown"
            rate_limit_key = identity.user_id if identity and identity.user_id else token or client_ip
            allowed, retry_after = consume_rate_limit(rate_limit_key)
            if not allowed:
                response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
                response.headers["Retry-After"] = str(retry_after)

        if response is None:
            response = await call_next(request)
        return response
    finally:
        duration_ms = int((perf_counter() - start) * 1000)
        if response is not None:
            response.headers["X-Request-ID"] = request_id
        if settings.audit_enabled and request.url.path.startswith("/api"):
            write_audit_log(
                SessionLocal,
                request_id=request_id,
                event_type="http",
                action="request",
                method=request.method,
                path=request.url.path,
                resource_id=None,
                detail=None,
                status_code=response.status_code if response is not None else 500,
                client_ip=request.client.host if request.client else None,
                user_id=identity.user_id if identity else None,
                duration_ms=duration_ms,
            )

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(research_harness_router)
