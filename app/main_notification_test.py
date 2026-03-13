import asyncio
from app.services.notification.senders.firebase_sender import FirebasePushNotificationSender
from app.core.notification.context import NotificationContext
from app.models import Project, Service, Incident, UserDeviceToken
from app.core.firebase import init_firebase
from dotenv import load_dotenv

load_dotenv()  # ← 이 한 줄이 핵심

async def main():

    init_firebase()
    ctx = NotificationContext(
        project=Project(id=1, name="Test Project"),
        service=Service(id=1, name="Test Service"),
        incident=Incident(id=999, title="Test Incident"),
        devices=[
            UserDeviceToken(
                token="dxGm-KOvTjqH3Rz4-dqi5Y:APA91bFkGUfPAswPHRkIqJjkeBL8GzKfCq_9eA3cDlXlNFrWtpe5kpQgDs7nmy-YI5yABORForsYbNLuOadSQJZvAXceUUO0xOrC3nl9lS3nMfvZGfanMh0",
                is_active=True,
            )
        ],
    )

    sender = FirebasePushNotificationSender()
    sender.send(ctx)


if __name__ == "__main__":
    asyncio.run(main())