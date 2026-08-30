import uuid
import logging
from fastapi import FastAPI,HTTPException,Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.api.routes import account,auth,billing,conversations,settings,telegram
from app.config import get_settings
from app.db.session import SessionLocal
s=get_settings(); app=FastAPI(title="Piklove AI Copilot",docs_url="/docs" if s.environment!="production" else None)
logger=logging.getLogger("piklove")
app.add_middleware(CORSMiddleware,allow_origins=[s.web_origin],allow_credentials=True,allow_methods=["GET","POST","PATCH","PUT","DELETE"],allow_headers=["Content-Type","Idempotency-Key"])
@app.middleware("http")
async def security(request:Request,call_next):
 request.state.request_id=str(uuid.uuid4()); response=await call_next(request); response.headers.update({"X-Request-ID":request.state.request_id,"X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer","Content-Security-Policy":"default-src 'none'; frame-ancestors 'none'"}); return response
def error_response(request:Request,status_code:int,code:str,message:str|None=None):
 return JSONResponse({"error":{"code":code,"message":message or code.replace("_"," ").title(),"request_id":request.state.request_id}},status_code=status_code)
@app.exception_handler(HTTPException)
async def http_errors(request:Request,exc:HTTPException):
 return error_response(request,exc.status_code,str(exc.detail))
@app.exception_handler(RequestValidationError)
async def validation_errors(request:Request,exc:RequestValidationError):
 return error_response(request,422,"VALIDATION_ERROR","Request validation failed")
@app.exception_handler(Exception)
async def unexpected_errors(request:Request,exc:Exception):
 logger.exception("unhandled request error",extra={"request_id":request.state.request_id})
 return error_response(request,500,"INTERNAL_ERROR","Internal server error")
for r in (auth.router,telegram.router,conversations.router,settings.router,billing.router,account.router): app.include_router(r,prefix="/api/v1")
@app.get("/health/live")
async def live(): return {"status":"ok"}
@app.get("/health/ready")
async def ready():
 try:
  async with SessionLocal() as db: await db.execute(text("SELECT 1"))
  return {"status":"ready"}
 except Exception:
  logger.exception("readiness database check failed")
  return JSONResponse({"status":"not_ready"},status_code=503)
