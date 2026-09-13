"""Simple FastAPI server exposing the BankResearchGateway as an HTTP API."""
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

logging.basicConfig(level="INFO")
app = FastAPI(title="Bank Research Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Lazy-load the gateway so import errors surface on first request, not at startup
_gateway = None

def get_gateway():
    global _gateway
    if _gateway is None:
        from app.agent import BankResearchGateway
        _gateway = BankResearchGateway()
    return _gateway


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        gateway = get_gateway()
        loop = asyncio.get_event_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            response = await loop.run_in_executor(pool, gateway.process_request, req.message)
        return {"response": response}
    except Exception as e:
        logging.error(f"Chat error: {e}")
        return {"response": f"Error: {str(e)}"}


# Serve the frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
