# Design: Propagación de provider_id a Conversation

**Fecha:** 2026-04-10  
**Issue relacionada:** #16 — Propagar el provider_id a las conversaciones  
**Scope:** jota-db — schema + endpoints /chat/conversations

---

## Contexto

Las conversaciones tienen un `model_id` que referencia un `AIModel` local, pero no registran qué `InferenceProvider` gestiona la inferencia. Sin este dato, el Orchestrator no puede saber qué backend usó (ni cuál usar) al retomar una conversación.

Los checkeos de items ya confirmados:
- `InferenceProvider.api_key` ya existe (`Optional[str]`, nullable) — no requiere cambio.
- `GET /internal/providers` ya expone `api_key` a través de `response_model=List[InferenceProvider]` — no requiere cambio.

---

## Cambios requeridos

### 1. Modelo `Conversation` — añadir `provider_id`

**Archivo:** `src/core/models.py`

Añadir a `Conversation`:
```python
provider_id: Optional[str] = Field(default=None, foreign_key="inferenceprovider.id")
provider: Optional["InferenceProvider"] = Relationship(back_populates="conversations")
```

Añadir a `InferenceProvider`:
```python
conversations: List["Conversation"] = Relationship(back_populates="provider")
```

El campo es nullable: una conversación puede existir sin provider asignado (casos locales o legacy).

### 2. DTO `ConversationCreate` — añadir `provider_id`

**Archivo:** `src/api/routers/chat.py`

```python
class ConversationCreate(BaseModel):
    title: Optional[str] = None
    model_id: Optional[str] = None
    provider_id: Optional[str] = None  # NUEVO
```

**Handler `POST /chat/conversations`:** si `provider_id` está presente, verificar que el `InferenceProvider` existe en DB. Si no → 404.

### 3. DTO `ConversationUpdate` — añadir `provider_id`

```python
class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    model_id: Optional[str] = None
    status: Optional[str] = None
    provider_id: Optional[str] = None  # NUEVO — permite quitar (enviar null)
```

**Handler `PATCH /chat/conversations/{id}`:** si `provider_id` está en el payload:
- Si es `null` → desasignar (guardar `None`).
- Si es un UUID → verificar que el provider existe. Si no → 404.

La lógica debe distinguir "campo no enviado" de "campo enviado como null". Se usa `model_dump(exclude_unset=True)` para ello — ya es el patrón del proyecto en `/admin/providers`.

---

## Comportamiento de errores

| Situación | Código |
|---|---|
| `provider_id` no existe en DB | 404 |
| `provider_id` válido pero provider inactivo | Permitido (no bloqueamos — la validación de disponibilidad es responsabilidad del Orchestrator) |
| `provider_id` omitido | Se ignora, sin cambio |
| `provider_id: null` explícito en PATCH | Se desasigna |

---

## Out of scope

- Migración de datos: las conversaciones existentes quedan con `provider_id = null`.
- Validación de que el provider está activo al crear/actualizar: se delega al Orchestrator.
- Refactor de `model_id` en `Conversation` (actualmente FK a `AIModel` local, pero los modelos los gestiona el provider externamente — issue separada).

---

## Cierre de issues

- Issue #16: se cierra con el PR que implemente estos cambios.
