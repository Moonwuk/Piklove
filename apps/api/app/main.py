import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import account, auth, billing, conversations, settings, telegram
from app.config import get_settings
from app.db.session import SessionLocal

s = get_settings()
app = FastAPI(
    title="Piklove AI Copilot", docs_url="/docs" if s.environment != "production" else None
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[s.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def security(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers.update(
        {
            "X-Request-ID": request.state.request_id,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return response


@app.exception_handler(Exception)
async def errors(request, exc):
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        return JSONResponse(
            {
                "error": {
                    "code": str(exc.detail),
                    "message": str(exc.detail).replace("_", " ").title(),
                    "request_id": request.state.request_id,
                }
            },
            status_code=exc.status_code,
        )
    return JSONResponse(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "request_id": request.state.request_id,
            }
        },
        status_code=500,
    )


for r in (
    auth.router,
    telegram.router,
    conversations.router,
    settings.router,
    billing.router,
    account.router,
):
    app.include_router(r, prefix="/api/v1")


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
