from fastapi import FastAPI, HTTPException

app = FastAPI(title="Inventory Service")

# Chaos flag
crashed = False

@app.get("/api/inventory/check")
def check_availability(eventId: str, seatId: str):
    if crashed:
        raise HTTPException(status_code=500, detail="Servicio de inventario no disponible (CHAOS)")
    
    return {"eventId": eventId, "seatId": seatId, "available": True}

@app.post("/api/inventory/reserve")
def reserve_seat(request: dict):
    if crashed:
        raise HTTPException(status_code=500, detail="Servicio de inventario no disponible (CHAOS)")
    
    return {"reserved": True, "eventId": request.get("eventId"), "seatId": request.get("seatId")}

# === CHAOS ENDPOINTS ===
@app.post("/api/inventory/chaos/crash")
def activate_crash():
    global crashed
    crashed = True
    return "CHAOS: Inventario ahora está CAÍDO"

@app.post("/api/inventory/chaos/recover")
def recover():
    global crashed
    crashed = False
    return "Inventario recuperado"

@app.get("/api/inventory/chaos/status")
def chaos_status():
    return {"crashed": crashed}
