import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlmodel import SQLModel, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:pass@db:5432/brain")

# Configuración del engine con pool robusto para acceso concurrente
# Esto permite que múltiples servicios (API + futuro MCP) accedan sin conflictos
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,        # Verifica conexiones antes de usarlas
    pool_size=10,               # Conexiones base en el pool
    max_overflow=20,            # Conexiones adicionales bajo carga
    pool_timeout=30,            # Segundos de espera antes de fallar
    pool_recycle=3600,          # Recicla conexiones cada hora (evita conexiones obsoletas)
)

def bootstrap_system_clients(session: Session):
    """
    Carga los servicios internos 'core' desde variables de entorno.
    Estos son necesarios para que el sistema funcione (Orchestrator, Inference, Transcriptor).
    NO toca la tabla Client (usuarios/tablets).
    Es idempotente: si ya existen, no hace nada.
    """
    from src.core.models import InternalService
    from sqlmodel import select

    # Definir los servicios requeridos
    services = [
        {
            "id": os.getenv("INTERNAL_ORCHESTRATOR_ID"),
            "key": os.getenv("INTERNAL_ORCHESTRATOR_KEY")
        },
        {
            "id": os.getenv("INTERNAL_INFERENCE_ID"),
            "key": os.getenv("INTERNAL_INFERENCE_KEY")
        },
        {
            "id": os.getenv("INTERNAL_TRANSCRIPTOR_ID"),
            "key": os.getenv("INTERNAL_TRANSCRIPTOR_KEY")
        },
        {
            "id": os.getenv("INTERNAL_SPEAKER_ID"),
            "key": os.getenv("INTERNAL_SPEAKER_KEY")
        },
        {
            "id": os.getenv("INTERNAL_GATEWAY_ID"),
            "key": os.getenv("INTERNAL_GATEWAY_KEY")
        }

    ]

    print("🚀 Verificando servicios internos (Bootstrap)...")
    
    for svc in services:
        if not svc["id"] or not svc["key"]:
            print(f"⚠️  Faltan credenciales para un servicio interno en .env. Saltando...")
            continue

        # Verificar existencia
        statement = select(InternalService).where(InternalService.id == svc["id"])
        existing = session.exec(statement).first()

        if not existing:
            print(f"🛠️  Creando servicio interno: {svc['id']}")
            new_service = InternalService(
                id=svc["id"],
                api_key=svc["key"],
                is_active=True
            )
            session.add(new_service)
        else:
            print(f"✅ Servicio interno ya existe: {svc['id']}")
    
    session.commit()

def sync_local_models(session: Session):
    """
    Escanea el directorio definido en MODELS_DIR (por defecto './models')
    y registra automáticamente los .gguf nuevos en la DB.
    Los modelos deben estar en carpetas con su mismo nombre (ej: models/llama3/llama3.gguf).
    """
    from src.core.models import AIModel
    from sqlmodel import select
    
    models_dir = os.getenv("MODELS_DIR", "./models")
    host_models_dir = os.getenv("HOST_MODELS_DIR")
    if not host_models_dir:
        print("⚠️ HOST_MODELS_DIR no está definida. Los file_path de los modelos se guardarán con la ruta del contenedor.")
        host_models_dir = models_dir
    if not os.path.exists(models_dir):
        print(f"⚠️ El directorio de modelos '{models_dir}' no existe. Saltando sincronización...")
        return

    print(f"🚀 Escaneando directorio de modelos: {models_dir} (Host config: {host_models_dir})")
    
    for folder_name in os.listdir(models_dir):
        folder_path = os.path.join(models_dir, folder_name)
        
        if os.path.isdir(folder_path):
            # El archivo debe llamarse igual que la carpeta + .gguf
            filename = f"{folder_name}.gguf"
            file_path = os.path.join(folder_path, filename)
            host_file_path = os.path.join(host_models_dir, folder_name, filename)
            
            if os.path.exists(file_path):
                model_id = folder_name
                
                # Verificar si ya existe por ID o file_path
                statement = select(AIModel).where((AIModel.id == model_id) | (AIModel.file_path == host_file_path))
                existing = session.exec(statement).first()
                
                if not existing:
                    print(f"🛠️  Registrando nuevo modelo: {model_id}")
                    new_model = AIModel(
                        id=model_id,
                        name=model_id.replace("-", " ").title(),
                        file_path=host_file_path,
                        description=f"Modelo auto-descubierto en carpeta: {folder_name}"
                    )
                    session.add(new_model)
                else:
                    if existing.file_path != host_file_path:
                        print(f"🔄 Actualizando ruta del modelo {model_id} a la del host")
                        existing.file_path = host_file_path
                        session.add(existing)
                    else:
                        print(f"✅ Modelo {model_id} ya registrado y ruta actualizada.")
                
    session.commit()

def bootstrap_clients(session: Session):
    """
    Carga los clientes externos (ej: Desktop App) desde variables de entorno.
    """
    from src.core.models import Client, ClientConfig, ClientType
    from sqlmodel import select

    import json
    
    clients_to_load = []

    # 1. Cargar desde JOTA_CLIENTS (JSON List)
    # Ejemplo: JOTA_CLIENTS='[{"name": "Mobile", "key": "mobile_01"}, {"name": "Test", "key": "test_key"}]'
    jota_clients_env = os.getenv("JOTA_CLIENTS")
    if jota_clients_env:
        try:
            clients_to_load.extend(json.loads(jota_clients_env))
            print(f"📦 Cargados {len(clients_to_load)} clientes desde JOTA_CLIENTS")
        except json.JSONDecodeError as e:
            print(f"❌ Error al parsear JOTA_CLIENTS: {e}")
    print("🚀 Verificando clientes externos (Bootstrap)...")
    
    for c_data in clients_to_load:
        if not c_data["key"]:
            continue
            
        statement = select(Client).where(Client.client_key == c_data["key"])
        existing = session.exec(statement).first()
        
        if not existing:
             print(f"🛠️  Creando cliente: {c_data['name']}")
             new_client = Client(
                 id=c_data["name"],
                 name=c_data["name"],
                 client_key=c_data["key"],
                 client_type=ClientType(c_data.get("type", ClientType.CHAT).upper()),
                 is_active=True
             )
             session.add(new_client)
             session.flush()
             session.add(ClientConfig(client_id=new_client.id))
             print(f"🛠️  Creando ClientConfig para: {c_data['name']}")
        else:
             print(f"✅ Cliente ya existe: {c_data['name']}")
             new_type = ClientType(c_data.get("type", ClientType.CHAT).upper())
             if existing.client_type != new_type:
                 existing.client_type = new_type
                 session.add(existing)
                 print(f"🔄 Actualizando tipo de cliente {c_data['name']} a {new_type}")
             # Garantizar que tenga ClientConfig aunque sea un cliente antiguo
             config = session.exec(select(ClientConfig).where(ClientConfig.client_id == existing.id)).first()
             if not config:
                 session.add(ClientConfig(client_id=existing.id))
                 print(f"🛠️  Creando ClientConfig para cliente existente: {c_data['name']}")

    session.commit()

def bootstrap_admin(session: Session):
    """Crea el AdminUser desde ADMIN_KEY si no existe. Idempotente."""
    from src.core.models import AdminUser

    admin_key = os.getenv("ADMIN_KEY")
    if not admin_key:
        print("⚠️  ADMIN_KEY no definida. Usuario admin no creado.")
        return

    existing = session.get(AdminUser, "admin")
    if not existing:
        print("🛠️  Creando usuario admin...")
        session.add(AdminUser(id="admin", api_key=admin_key, is_active=True))
        session.commit()  # commit único aquí: bootstrap_admin es siempre la primera llamada del bloque admin
    else:
        print("✅ Usuario admin ya existe.")


def seed_inference_providers(session: Session):
    """
    Puebla la tabla inference_provider desde env si está vacía.
    Provider local siempre. Externos solo si tienen API key.

    NOTA: La idempotencia es a nivel de tabla (salta si existe cualquier fila).
    Si se añaden nuevas SEED_*_API_KEY post-arranque inicial, añadir los
    providers manualmente vía POST /admin/providers o vaciar la tabla.
    """
    from src.core.models import InferenceProvider, ProviderType
    from sqlmodel import select

    existing = session.exec(select(InferenceProvider)).first()
    if existing:
        print("✅ InferenceProviders ya existen. Saltando seed.")
        return

    print("🚀 Seeding inference providers...")

    # Provider local (siempre)
    local_url = os.getenv("SEED_LOCAL_PROVIDER_URL", "ws://jota-inference:8002")
    local_model = os.getenv("SEED_LOCAL_MODEL_ID", "llama-3.2-3b")
    session.add(InferenceProvider(
        name="Local (jota-inference)",
        type=ProviderType.local,
        base_url=local_url,
        default_model_id=local_model,
        is_active=True,
    ))
    print(f"  ✅ Local provider: {local_url}")

    # OpenAI (solo si hay API key)
    openai_key = os.getenv("SEED_OPENAI_API_KEY")
    if openai_key:
        openai_model = os.getenv("SEED_OPENAI_DEFAULT_MODEL", "gpt-4o")
        session.add(InferenceProvider(
            name="OpenAI",
            type=ProviderType.openai,
            api_key=openai_key,
            default_model_id=openai_model,
            is_active=True,
        ))
        print(f"  ✅ OpenAI provider: {openai_model}")

    # Anthropic (solo si hay API key)
    anthropic_key = os.getenv("SEED_ANTHROPIC_API_KEY")
    if anthropic_key:
        anthropic_model = os.getenv("SEED_ANTHROPIC_DEFAULT_MODEL", "claude-sonnet-4-6")
        session.add(InferenceProvider(
            name="Anthropic",
            type=ProviderType.anthropic,
            api_key=anthropic_key,
            default_model_id=anthropic_model,
            is_active=True,
        ))
        print(f"  ✅ Anthropic provider: {anthropic_model}")

    session.commit()


def seed_service_config(session: Session):
    """
    Puebla service_config desde env si está vacía.
    Debe llamarse DESPUÉS de seed_inference_providers (necesita el UUID del provider local).
    """
    from src.core.models import ServiceConfig, InferenceProvider, ProviderType
    from sqlmodel import select

    existing = session.exec(select(ServiceConfig)).first()
    if existing:
        print("✅ ServiceConfig ya existe. Saltando seed.")
        return

    print("🚀 Seeding service config...")

    entries = []

    # Transcriber
    transcriber_model = os.getenv("SEED_TRANSCRIBER_MODEL", "whisper-large-v3")
    entries.append(ServiceConfig(
        service="transcriber", key="model",
        value=transcriber_model,
        description="Modelo de Whisper a usar",
    ))
    chunk_ms = os.getenv("SEED_TRANSCRIBER_AUDIO_CHUNK_MS", "200")
    entries.append(ServiceConfig(
        service="transcriber", key="audio.chunk_ms",
        value=int(chunk_ms),
        description="Tamaño de chunk de audio en ms",
    ))

    # Speaker
    speaker_model = os.getenv("SEED_SPEAKER_MODEL", "kokoro-v1")
    entries.append(ServiceConfig(
        service="speaker", key="model",
        value=speaker_model,
        description="Modelo TTS a usar",
    ))

    # Orchestrator — apunta al provider local (ya debe existir en DB)
    local_provider = session.exec(
        select(InferenceProvider).where(InferenceProvider.type == ProviderType.local)
    ).first()
    if not local_provider:
        print("⚠️  No se encontró local provider. orchestrator.default_provider_id quedará None.")
    default_provider_id = local_provider.id if local_provider else None
    entries.append(ServiceConfig(
        service="orchestrator", key="default_provider_id",
        value=default_provider_id,
        description="UUID del InferenceProvider por defecto",
    ))
    entries.append(ServiceConfig(
        service="orchestrator", key="fallback_provider_id",
        value=None,
        description="UUID del InferenceProvider de fallback (null = sin fallback)",
    ))

    for entry in entries:
        session.add(entry)
    session.commit()
    print(f"  ✅ {len(entries)} entradas de config creadas.")


def init_db():
    """
    Inicializa la base de datos: verifica la conexión y crea las tablas.
    
    NOTA: Se usa SQLModel.metadata.create_all(engine) para auto-provisionamiento.
    No se requiere Alembic para el primer arranque.
    
    Incluye lógica de reintento robusta para esperar a que PostgreSQL esté listo.
    """
    retries = 5
    while retries > 0:
        try:
            print(f"🔄 Intentando conectar a la DB... (Reintentos restantes: {retries})")
            # Importamos los modelos aquí para evitar importaciones circulares
            from src.core import models  # noqa: F401
            
            # Verificar conexión sin crear tablas
            with Session(engine) as session:
                session.exec(text("SELECT 1"))
            
            print("✅ Base de datos conectada exitosamente.")
            
            # Crear tablas automáticamente (sin Alembic por ahora)
            print("📦 Creando tablas en la base de datos...")
            SQLModel.metadata.create_all(engine)

            # Bootstrap de datos
            with Session(engine) as session:
                bootstrap_system_clients(session)
                bootstrap_clients(session)
                sync_local_models(session)
                bootstrap_admin(session)
                seed_inference_providers(session)
                seed_service_config(session)
            
            print("🚀 Sistema inicializado correctamente.")
            break
        except OperationalError as e:
            retries -= 1
            print(f"⚠️ La DB no está lista aún. Esperando 3 segundos... (Error: {e})")
            time.sleep(3)
    
    if retries == 0:
        print("❌ Error crítico: No se pudo conectar a la base de datos después de varios intentos.")
        raise Exception("Database connection failed")

def get_session():
    """
    Generador de sesiones para FastAPI o scripts.
    Usa 'yield' para asegurar que la sesión se cierre después de usarse.
    """
    with Session(engine) as session:
        yield session