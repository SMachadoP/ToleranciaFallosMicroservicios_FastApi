# Sistema de Reservas de Entradas - Tolerancia a Fallos en Sistemas Distribuidos

## Arquitectura

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Cliente   │────▶│    NGINX     │────▶│   Reservation   │
└─────────────┘     │ Rate Limiting│     │    Service      │
                    └──────────────┘     └───────┬─────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                            │                            │
              ┌─────▼─────┐               ┌──────▼──────┐              ┌──────▼──────┐
              │ Inventory │               │   Payment   │              │Notification │
              │  Service  │               │   Service   │              │   Service   │
              └───────────┘               └─────────────┘              └─────────────┘
```

## Patrones Implementados

| Fallo | Patrón | Implementación |
|-------|--------|----------------|
| **Inventario Fantasma** | Circuit Breaker | `circuitbreaker` library |
| **Pasarela Lenta** | Timeout (5s) + Retry (3 intentos) | `httpx` + `tenacity` |
| **Diluvio de Peticiones** | Rate Limiting (2r/s) | NGINX `limit_req` |
| **Correo Perdido** | Async fire-and-forget | `BackgroundTasks` |

## Requisitos

- Docker y Docker Compose

## Ejecución

```powershell
cd TolerenciaFallosFastApi
docker-compose up --build
```

Esperar hasta ver `Uvicorn running` está listo.

---

## Demo de Fallos (PowerShell)

### 0. Reserva Normal (Verificar que funciona)

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost/api/reservations" -ContentType "application/json" -Body '{"eventId":"EVT-001","seatId":"A1","userEmail":"test@email.com","amount":50.0}'
```

**Resultado esperado:**
```
success reservationId message
------- ------------- -------
   True             1 Reserva confirmada exitosamente
```

---

### 1. Inventario Fantasma (Circuit Breaker)

```powershell
# 1. Activar crash del inventario
Invoke-RestMethod -Method POST -Uri "http://localhost:8082/api/inventory/chaos/crash"

# 2. Intentar reserva (DEBE FALLAR)
Invoke-RestMethod -Method POST -Uri "http://localhost/api/reservations" -ContentType "application/json" -Body '{"eventId":"EVT-001","seatId":"A2","userEmail":"test@email.com","amount":50.0}'

# 3. Recuperar inventario
Invoke-RestMethod -Method POST -Uri "http://localhost:8082/api/inventory/chaos/recover"

# 4. Verificar que funciona de nuevo
Invoke-RestMethod -Method POST -Uri "http://localhost/api/reservations" -ContentType "application/json" -Body '{"eventId":"EVT-001","seatId":"A2","userEmail":"test@email.com","amount":50.0}'
```

**Resultado esperado:** Error 503 cuando está caído, éxito después de recuperar.

---

### 2. Pasarela Lenta (Timeout + Retry)

```powershell
# 1. Activar latencia de 20 segundos
Invoke-RestMethod -Method POST -Uri "http://localhost:8083/api/payments/chaos/slow?delay=20"

# 2. Intentar reserva (DEBE FALLAR después de ~15s por reintentos)
Invoke-RestMethod -Method POST -Uri "http://localhost/api/reservations" -ContentType "application/json" -Body '{"eventId":"EVT-001","seatId":"A3","userEmail":"test@email.com","amount":50.0}'

# 3. Restaurar pagos
Invoke-RestMethod -Method POST -Uri "http://localhost:8083/api/payments/chaos/normal"

# 4. Verificar que funciona
Invoke-RestMethod -Method POST -Uri "http://localhost/api/reservations" -ContentType "application/json" -Body '{"eventId":"EVT-001","seatId":"A3","userEmail":"test@email.com","amount":50.0}'
```

**Resultado esperado:** Timeout después de 5s por intento × 3 reintentos = fallo controlado.

---

### 3. Diluvio de Peticiones (Rate Limiting)

```powershell
for ($i=1; $i -le 15; $i++) {
    try {
        $r = Invoke-RestMethod -Method POST -Uri "http://localhost/api/reservations" -ContentType "application/json" -Body '{"eventId":"EVT-001","seatId":"A1","userEmail":"test@email.com","amount":50.0}'
        Write-Host "$i OK"
    } catch {
        Write-Host "$i BLOQUEADO" -ForegroundColor Red
    }
}
```

**Resultado esperado:**
```
1 OK
2 OK
3 OK
4 OK
5 OK
6 OK
7 BLOQUEADO
8 BLOQUEADO
...
```
(Primeras 6 pasan por burst, luego se bloquean)

---

### 4. Correo Perdido (Async graceful)

```powershell
# 1. Desactivar notificaciones
Invoke-RestMethod -Method POST -Uri "http://localhost:8084/api/notifications/chaos/disable"

# 2. Hacer reserva (DEBE FUNCIONAR aunque notificaciones estén caídas)
Invoke-RestMethod -Method POST -Uri "http://localhost/api/reservations" -ContentType "application/json" -Body '{"eventId":"EVT-001","seatId":"A99","userEmail":"test@email.com","amount":50.0}'

# 3. Reactivar notificaciones
Invoke-RestMethod -Method POST -Uri "http://localhost:8084/api/notifications/chaos/enable"
```

**Resultado esperado:** `Reserva confirmada exitosamente` (aunque notificaciones fallen).

---

## Puertos

| Servicio | Puerto |
|----------|--------|
| NGINX (API Gateway) | 80 |
| Inventario | 8082 |
| Pagos | 8083 |
| Notificaciones | 8084 |

## Detener

```powershell
docker-compose down
```

## Ver logs

```powershell
docker-compose logs reservation-service
docker-compose logs inventory-service
```
