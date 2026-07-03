# Legacy Tasks & Events API

> ⚠️ **DEPRECATED.** This API surface was part of an earlier iteration of `jota-db`. It is no longer part of the active system and is kept here only for historical reference and to support external integrations that may still call it.

The endpoints documented below (`/tasks`, `/events`) are present in some older deployments but are not part of the current Jota architecture. The current role of `jota-db` is centralized authentication for legacy service setups — see the [main README](../README.md).

---

## Tasks (legacy)

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

## Events (legacy)

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
