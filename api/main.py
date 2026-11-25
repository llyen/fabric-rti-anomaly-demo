"""
Demo API ruchu HTTP instrumentowane przez Azure Monitor OpenTelemetry.

Każde żądanie generuje telemetrię "request" (AppRequests) wysyłaną do
Application Insights. To te dane są następnie strumieniowane do Microsoft Fabric
i analizowane pod kątem anomalii.

Uruchomienie:
    pip install -r requirements.txt
    copy .env.example .env   # i uzupełnij APPLICATIONINSIGHTS_CONNECTION_STRING
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
import asyncio
import os
import random

from dotenv import load_dotenv

load_dotenv()

# Konfiguracja Azure Monitor MUSI nastąpić przed utworzeniem aplikacji,
# aby auto-instrumentacja FastAPI przechwyciła wszystkie żądania.
from azure.monitor.opentelemetry import configure_azure_monitor  # noqa: E402

_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if _conn:
    configure_azure_monitor(
        connection_string=_conn,
        # cloud_RoleName w App Insights / kolumnie AppRoleName w Fabric
        resource_attributes={"service.name": os.getenv("OTEL_SERVICE_NAME", "orders-api")},
    )

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

app = FastAPI(title="Fabric Anomaly Demo API")

# Endpointy reprezentują typowy ruch w aplikacji e-commerce.
PRODUCTS = [f"sku-{i:03d}" for i in range(1, 51)]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/products")
async def list_products():
    # Lekki, szybki endpoint (niska latencja).
    await asyncio.sleep(random.uniform(0.01, 0.05))
    return {"products": PRODUCTS[:20]}


@app.get("/api/products/{sku}")
async def get_product(sku: str):
    await asyncio.sleep(random.uniform(0.02, 0.08))
    if sku not in PRODUCTS:
        raise HTTPException(status_code=404, detail="product not found")
    return {"sku": sku, "price": round(random.uniform(10, 500), 2)}


@app.post("/api/checkout")
async def checkout(request: Request):
    # Cięższy endpoint: wyższa, zmienna latencja (cel do wykrywania anomalii latencji).
    await asyncio.sleep(random.uniform(0.10, 0.30))
    # ~2% naturalnych błędów (np. odrzucona płatność).
    if random.random() < 0.02:
        raise HTTPException(status_code=402, detail="payment declined")
    return {"order_id": random.randint(100000, 999999), "status": "confirmed"}


@app.get("/api/search")
async def search(q: str = ""):
    await asyncio.sleep(random.uniform(0.05, 0.15))
    return {"query": q, "hits": random.randint(0, 200)}


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    # Zwracamy strukturę, ale status code jest kluczowy dla telemetrii AppRequests.
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
