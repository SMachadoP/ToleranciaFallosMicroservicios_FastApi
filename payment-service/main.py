from fastapi import FastAPI
import time

app = FastAPI(title="Payment Service")

# Chaos: latency in seconds
latency_seconds = 0

@app.post("/api/payments/process")
def process_payment(request: dict):
    # CHAOS: inject latency
    if latency_seconds > 0:
        print(f"[CHAOS] Inyectando latencia de {latency_seconds}s")
        time.sleep(latency_seconds)
    
    return {
        "success": True,
        "transactionId": f"TXN-{int(time.time())}",
        "amount": request.get("amount")
    }

# === CHAOS ENDPOINTS ===
@app.post("/api/payments/chaos/slow")
def activate_slow(delay: int = 20):
    global latency_seconds
    latency_seconds = delay
    return f"CHAOS: Pagos ahora tiene latencia de {delay}s"

@app.post("/api/payments/chaos/normal")
def normal_mode():
    global latency_seconds
    latency_seconds = 0
    return "Pagos funcionando normalmente"

@app.get("/api/payments/chaos/status")
def chaos_status():
    return {"latencySeconds": latency_seconds}
