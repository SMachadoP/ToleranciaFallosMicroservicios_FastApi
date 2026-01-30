from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from circuitbreaker import circuit
from tenacity import retry, stop_after_attempt, wait_fixed
import httpx
import os
import time
from datetime import datetime

app = FastAPI(title="Reservation Service")

# Database with retry for startup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@localhost:5432/reservations")

# Retry database connection on startup
def get_engine():
    for attempt in range(10):
        try:
            engine = create_engine(DATABASE_URL)
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"[DB] Conectado a la base de datos")
            return engine
        except Exception as e:
            print(f"[DB] Intento {attempt+1}/10 - Esperando base de datos... {e}")
            time.sleep(3)
    raise Exception("No se pudo conectar a la base de datos")

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String)
    seat_id = Column(String)
    user_email = Column(String)
    status = Column(String, default="CONFIRMED")
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# External service URLs
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:8001")
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://localhost:8002")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8003")

# Request model
class ReservationRequest(BaseModel):
    eventId: str
    seatId: str
    userEmail: str
    amount: float

# === CIRCUIT BREAKER for Inventory ("Inventario Fantasma") ===
@circuit(failure_threshold=3, recovery_timeout=10)
def check_inventory(event_id: str, seat_id: str) -> bool:
    with httpx.Client(timeout=5.0) as client:
        response = client.get(f"{INVENTORY_URL}/api/inventory/check", 
                              params={"eventId": event_id, "seatId": seat_id})
        response.raise_for_status()
        return response.json().get("available", False)

def inventory_fallback(event_id: str, seat_id: str) -> bool:
    print(f"[CIRCUIT BREAKER] Inventario caído. Fallback activado.")
    return False

# === TIMEOUT + RETRY for Payment ("Pasarela Lenta") ===
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def process_payment(amount: float, email: str) -> bool:
    with httpx.Client(timeout=5.0) as client:  # 5 second timeout
        response = client.post(f"{PAYMENT_URL}/api/payments/process",
                               json={"amount": amount, "email": email})
        response.raise_for_status()
        return response.json().get("success", False)

# === ASYNC NOTIFICATION ("Correo Perdido") ===
async def send_notification_async(email: str, reservation_id: int):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{NOTIFICATION_URL}/api/notifications/send",
                              json={"email": email, "reservationId": reservation_id})
        print(f"[NOTIFICATION] Email enviado a: {email}")
    except Exception as e:
        # Fire-and-forget: log but don't fail
        print(f"[NOTIFICATION] Fallo al enviar email (no crítico): {e}")

@app.post("/api/reservations")
async def create_reservation(request: ReservationRequest, background_tasks: BackgroundTasks):
    # 1. Check inventory (Circuit Breaker)
    try:
        inventory_ok = check_inventory(request.eventId, request.seatId)
    except Exception:
        inventory_ok = inventory_fallback(request.eventId, request.seatId)
    
    if not inventory_ok:
        raise HTTPException(status_code=503, 
                           detail={"success": False, "message": "Inventario no disponible o servicio temporalmente inactivo"})
    
    # 2. Process payment (Timeout + Retry)
    try:
        payment_ok = process_payment(request.amount, request.userEmail)
    except Exception as e:
        print(f"[PAYMENT] Fallo después de reintentos: {e}")
        raise HTTPException(status_code=503,
                           detail={"success": False, "message": "Error procesando pago. Intente más tarde."})
    
    if not payment_ok:
        raise HTTPException(status_code=503,
                           detail={"success": False, "message": "Pago rechazado."})
    
    # 3. Save reservation
    db = SessionLocal()
    reservation = Reservation(
        event_id=request.eventId,
        seat_id=request.seatId,
        user_email=request.userEmail,
        status="CONFIRMED"
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    db.close()
    
    # 4. Send notification async (fire-and-forget)
    background_tasks.add_task(send_notification_async, request.userEmail, reservation.id)
    
    return {
        "success": True,
        "reservationId": reservation.id,
        "message": "Reserva confirmada exitosamente"
    }

@app.get("/api/reservations/health")
def health():
    return {"status": "OK"}
