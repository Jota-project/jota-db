
from sqlmodel import Session, select
from src.core.database import engine
from src.core.models import Client, InternalService

def init_data():
    with Session(engine) as session:
        # Create Test Client
        client = session.exec(select(Client).where(Client.client_key == "test_client_key")).first()
        if not client:
            client = Client(name="Test Client", client_key="test_client_key")
            session.add(client)
            print("Created Test Client")
        else:
            print("Test Client already exists")
            
        # Create Test Service
        service = session.exec(select(InternalService).where(InternalService.api_key == "test_service_key")).first()
        if not service:
            service = InternalService(client_id="TestService", api_key="test_service_key", role="admin")
            session.add(service)
            print("Created Test Service")
        else:
            print("Test Service already exists")
            
        session.commit()
        print(f"Client ID: {client.id}")

if __name__ == "__main__":
    init_data()
