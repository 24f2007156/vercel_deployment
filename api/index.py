import json
import math
import os
from typing import List
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

app = FastAPI()

# 1. Custom Middleware: Brute-force CORS headers onto EVERY response
@app.middleware("http")
async def force_cors(request: Request, call_next):
    # Handle preflight OPTIONS requests directly
    if request.method == "OPTIONS":
        response = Response()
    else:
        response = await call_next(request)
        
    # Inject headers unconditionally
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

class QueryPayload(BaseModel):
    regions: List[str]
    threshold_ms: float

def get_percentile(data, p):
    if not data: return 0.0
    s_data = sorted(data)
    k = (len(s_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c: return s_data[int(k)]
    return s_data[int(f)] * (c - k) + s_data[int(c)] * (k - f)

@app.post("/{full_path:path}")
def handle_post(full_path: str, payload: QueryPayload):
    return process_metrics(payload)

@app.post("/")
def handle_post_root(payload: QueryPayload):
    return process_metrics(payload)

def process_metrics(payload: QueryPayload):
    try:
        data_path = os.path.join(os.path.dirname(__file__), "..", "telemetry.json")
        with open(data_path, "r") as f:
            telemetry_data = json.load(f)
    except Exception:
        try:
            with open("telemetry.json", "r") as f:
                telemetry_data = json.load(f)
        except Exception:
            telemetry_data = []

    results = {}
    for region in payload.regions:
        region_data = [d for d in telemetry_data if d.get("region") == region]
        if not region_data:
            continue
            
        latencies = [d["latency_ms"] for d in region_data]
        uptimes = [d["uptime_pct"] for d in region_data]
        
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = get_percentile(latencies, 95)
        avg_uptime = sum(uptimes) / len(uptimes)
        breaches = sum(1 for l in latencies if l > payload.threshold_ms)
        
        results[region] = {
            "avg_latency": avg_latency,
            "p95_latency": p95_latency,
            "avg_uptime": avg_uptime,
            "breaches": breaches
        }
        
    return results