"""
Generator ruchu HTTP do demo API.

Tworzy realistyczny, zmienny w czasie wzorzec ruchu (baseline z falą "dobową"
przyspieszoną do minut) oraz na żądanie wstrzykuje anomalie, które mają zostać
wykryte w Fabric:

  - surge   : nagły skok wolumenu żądań (anomalia wolumenu),
  - errors  : seria błędów 5xx (anomalia poziomu błędów),
  - latency : wzrost latencji na /api/checkout (anomalia latencji).

Przykłady:
    python traffic_gen.py                      # ciągły baseline
    python traffic_gen.py --duration 1800      # 30 min baseline
    python traffic_gen.py --inject surge       # baseline + okresowe skoki
    python traffic_gen.py --inject errors,latency
    python traffic_gen.py --rps 8 --inject surge,errors,latency

Baseline RPS oscyluje sinusoidalnie, więc na wykresach widać "wzorzec ruchu",
a anomalie wyraźnie odstają od adaptacyjnego baseline'u.
"""
import argparse
import asyncio
import math
import os
import random
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# Rozkład ruchu na endpointy (suma wag nieistotna).
ENDPOINTS = [
    ("GET", "/api/products", 30),
    ("GET", "/api/products/{sku}", 25),
    ("GET", "/api/search", 20),
    ("POST", "/api/checkout", 15),
    ("GET", "/health", 10),
]
SKUS = [f"sku-{i:03d}" for i in range(1, 60)]  # część spoza katalogu -> 404


def pick_endpoint():
    total = sum(w for *_, w in ENDPOINTS)
    r = random.uniform(0, total)
    upto = 0
    for method, path, w in ENDPOINTS:
        upto += w
        if r <= upto:
            return method, path
    return ENDPOINTS[0][0], ENDPOINTS[0][1]


async def fire(client: httpx.AsyncClient, force_error: bool, force_latency: bool):
    method, path = pick_endpoint()
    params = {}
    headers = {}
    if "{sku}" in path:
        path = path.replace("{sku}", random.choice(SKUS))
    if path == "/api/search":
        params["q"] = random.choice(["shoes", "laptop", "phone", "", "xyz"])
    # Sygnały dla API, by wymusić anomalię po stronie serwera nie są potrzebne:
    # latencję i błędy generujemy przez dobór ścieżek/obciążenia po stronie klienta.
    if force_error:
        # uderzamy w nieistniejący zasób -> 404 (lub checkout -> okazjonalnie 402)
        method, path = "GET", f"/api/products/sku-{random.randint(900, 999)}"
    try:
        if force_latency and path == "/api/checkout":
            # symulacja wolnego klienta: wiele równoległych checkoutów
            pass
        if method == "POST":
            await client.post(path, timeout=10)
        else:
            await client.get(path, params=params, headers=headers, timeout=10)
    except Exception:
        pass


async def run(duration: int, base_rps: float, inject: set):
    start = time.time()
    cycle = 0
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        while duration == 0 or time.time() - start < duration:
            elapsed = time.time() - start
            # Fala "dobowa" przyspieszona: pełny cykl co 600 s.
            wave = 0.5 * (1 + math.sin(2 * math.pi * elapsed / 600.0))
            rps = base_rps * (0.5 + wave)  # 0.5x .. 1.5x baseline

            force_error = False
            force_latency = False

            # Anomalie wstrzykiwane okresowo, by były widoczne i powtarzalne.
            window = int(elapsed) % 300  # co 5 minut
            if "surge" in inject and 60 <= window < 90:
                rps *= 6.0  # gwałtowny skok wolumenu
            if "errors" in inject and 150 <= window < 175:
                force_error = True  # seria błędów
            if "latency" in inject and 230 <= window < 255:
                force_latency = True
                rps *= 2.0  # nawał ciężkich checkoutów

            n = max(1, int(rps))
            tasks = []
            for _ in range(n):
                ep_force_latency = force_latency
                tasks.append(fire(client, force_error, ep_force_latency))
                if force_latency:
                    # wymuś ruch na checkout, by podbić latencję percentyli
                    tasks.append(client.post("/api/checkout", timeout=10))
            await asyncio.gather(*tasks, return_exceptions=True)

            cycle += 1
            if cycle % 10 == 0:
                tag = ",".join(sorted(inject)) or "none"
                print(f"[t+{int(elapsed):4d}s] rps~{rps:5.1f} window={window:3d} inject={tag}")
            await asyncio.sleep(1.0)


def main():
    p = argparse.ArgumentParser(description="Generator ruchu do demo Fabric Anomaly Detection")
    p.add_argument("--duration", type=int, default=0, help="czas w sekundach (0 = bez końca)")
    p.add_argument("--rps", type=float, default=4.0, help="bazowy RPS (przed falą i anomaliami)")
    p.add_argument(
        "--inject",
        type=str,
        default="",
        help="anomalie do wstrzyknięcia: surge,errors,latency (po przecinku)",
    )
    args = p.parse_args()
    inject = {s.strip() for s in args.inject.split(",") if s.strip()}
    print(f"Target={BASE_URL} base_rps={args.rps} inject={inject or 'none'} duration={args.duration or 'inf'}")
    asyncio.run(run(args.duration, args.rps, inject))


if __name__ == "__main__":
    main()
