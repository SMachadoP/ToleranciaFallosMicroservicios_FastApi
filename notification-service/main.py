from fastapi import FastAPI, HTTPException

app = FastAPI(title="Notification Service")

# Chaos flag
disabled = False

@app.post("/api/notifications/send")
def send_notification(request: dict):
    if disabled:
        raise HTTPException(status_code=500, detail="Servicio de notificaciones no disponible (CHAOS)")
    
    print(f"[NOTIFICATION] Enviando email a: {request.get('email')} para reserva: {request.get('reservationId')}")
    return {"sent": True, "email": request.get("email")}

# === CHAOS ENDPOINTS ===
@app.post("/api/notifications/chaos/disable")
def disable():
    global disabled
    disabled = True
    return "CHAOS: Notificaciones DESACTIVADAS"

@app.post("/api/notifications/chaos/enable")
def enable():
    global disabled
    disabled = False
    return "Notificaciones activadas"

@app.get("/api/notifications/chaos/status")
def chaos_status():
    return {"disabled": disabled}
