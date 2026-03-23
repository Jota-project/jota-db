# Cerebro Digital - Guía de Uso

## 🚀 Inicio Rápido

### 1. Levantar los servicios

```bash
# Asegúrate de que Docker está corriendo
docker compose up --build -d

# Ver logs
docker compose logs -f api-server
```

### 2. Verificar que todo funciona

```bash
# Health check
curl http://localhost:8000/health

# Deberías ver: {"status":"ok","service":"Cerebro Digital API"}
```

## 📝 Ejemplos de Uso de la API

### Tasks (Tareas)

#### Crear una tarea
```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Preparar presentación",
    "status": "pending",
    "priority": 4,
    "timing_relative_to_event": "before"
  }'
```

#### Listar todas las tareas
```bash
curl http://localhost:8000/tasks
```

#### Filtrar tareas por estado
```bash
curl "http://localhost:8000/tasks?status_filter=pending"
```

#### Actualizar una tarea (con optimistic locking)
```bash
# Primero obtén la tarea para conocer su versión actual
curl http://localhost:8000/tasks/1

# Luego actualiza incluyendo la versión
curl -X PATCH http://localhost:8000/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "done",
    "version": 1
  }'
```

#### Eliminar una tarea
```bash
curl -X DELETE http://localhost:8000/tasks/1
```

### Events (Eventos)

#### Crear un evento
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Reunión con el equipo",
    "description": "Sprint planning Q1 2026",
    "start_at": "2026-02-05T10:00:00",
    "end_at": "2026-02-05T11:30:00",
    "location": "Sala de conferencias"
  }'
```

#### Listar eventos
```bash
curl http://localhost:8000/events
```

#### Filtrar eventos por rango de fechas
```bash
curl "http://localhost:8000/events?start_after=2026-02-01T00:00:00&start_before=2026-02-28T23:59:59"
```

### Reminders (Recordatorios)

#### Crear un recordatorio vinculado a una tarea
```bash
curl -X POST http://localhost:8000/reminders \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Revisar slides de la presentación",
    "trigger_at": "2026-02-04T18:00:00",
    "task_id": 1
  }'
```

#### Crear un recordatorio independiente
```bash
curl -X POST http://localhost:8000/reminders \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Llamar al dentista",
    "trigger_at": "2026-02-03T09:00:00"
  }'
```

#### Listar recordatorios pendientes
```bash
curl "http://localhost:8000/reminders?is_completed=false"
```

### Auth (Autenticación)

#### Validar servicio interno (InternalService)
```bash
curl "http://localhost:8000/auth/internal" \
  -H "X-Service-ID: JotaOrchestrator" \
  -H "X-API-Key: secret123" \
  -H "Authorization: Bearer <API_SECRET_KEY>"
```

#### Validar cliente externo (Client)
```bash
curl "http://localhost:8000/auth/client" \
  -H "X-API-Key: desktop_client_01" \
  -H "Authorization: Bearer <API_SECRET_KEY>"
```

### Chat (Conversación)

#### Iniciar una conversación
```bash
curl -X POST http://localhost:8000/chat/conversation \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "title": "Ayuda con Python"
  }'
```

#### Enviar un mensaje
```bash
curl -X POST http://localhost:8000/chat/1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "¿Cómo funciona asyncio?"
  }'
```

#### Obtener mensajes de una conversación
```bash
curl http://localhost:8000/chat/1/messages

# Con límite de mensajes
curl "http://localhost:8000/chat/1/messages?limit=10"
```

## 🔒 Optimistic Locking (Control de Concurrencia)

El sistema implementa **optimistic locking** para prevenir conflictos cuando múltiples servicios (API + futuro MCP) modifican los mismos datos.

### ¿Cómo funciona?

Cada registro tiene un campo `version` que se incrementa automáticamente en cada actualización.

### Ejemplo de conflicto detectado

```bash
# Usuario A obtiene la tarea (version=1)
curl http://localhost:8000/tasks/1
# {"id":1,"title":"Mi tarea","version":1,...}

# Usuario B también obtiene la tarea (version=1)
curl http://localhost:8000/tasks/1

# Usuario A actualiza primero (version pasa a 2)
curl -X PATCH http://localhost:8000/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"status":"doing","version":1}'

# Usuario B intenta actualizar con version=1 (¡CONFLICTO!)
curl -X PATCH http://localhost:8000/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"priority":5,"version":1}'

# Respuesta: HTTP 409 Conflict
# {"detail":"Version conflict: expected 2, got 1"}
```

### Buenas prácticas

1. **Siempre incluye el campo `version`** en tus actualizaciones
2. Si recibes un error 409, **vuelve a obtener el registro** actualizado
3. Revisa los cambios y **reaplica tu modificación** con la nueva versión

## 🗄️ Arquitectura de Base de Datos

### Connection Pool

El sistema está configurado para manejar múltiples servicios concurrentes:

- **pool_size**: 10 conexiones base
- **max_overflow**: 20 conexiones adicionales bajo carga
- **pool_recycle**: Recicla conexiones cada hora

### Índices de Performance

Se han creado índices en los campos más consultados:

- **Tasks**: `status`, `priority`, `event_id`
- **Events**: `start_at`, `end_at`
- **Reminders**: `trigger_at`, `task_id`, `event_id`, `is_completed`

## 🐳 Docker

### Comandos útiles

```bash
# Iniciar servicios
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f

# Detener servicios
docker compose down

# Detener y eliminar volúmenes (¡CUIDADO! Borra la DB)
docker compose down -v

# Reconstruir después de cambios en el código
docker compose up --build -d

# Acceder a la base de datos
docker exec -it jota_db psql -U user -d jota

# Gestión de Migraciones (Alembic)
# Generar una nueva migración (después de cambiar modelos)
docker compose exec api-server alembic revision --autogenerate -m "descripcion_cambios"

# Aplicar migraciones pendientes
docker compose exec api-server alembic upgrade head
```

### Seguridad

El contenedor de la API:

- ✅ Usa **Alpine Linux** (imagen mínima)
- ✅ **Multi-stage build** (reduce tamaño)
- ✅ Ejecuta como **usuario no-root** (`appuser`)
- ✅ Health checks configurados

## 📚 Próximos Pasos

1. **Implementar el servidor MCP** para integración con IAs
2. **Añadir autenticación** (JWT tokens)
3. **Crear tests automatizados** (pytest)
4. **Documentación automática** con Swagger UI (ya disponible en `/docs`)

## 🔗 Endpoints Útiles

- **API Docs (Swagger)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
