# import firebase_admin
# from firebase_admin import credentials
# import os
# import logging
#
# logger = logging.getLogger(__name__)
#
# # def init_firebase():
# #     if firebase_admin._apps:
# #         return  # 이미 초기화됨
# #
# #     if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
# #         logger.info("Initializing Firebase with service account file")
# #         cred = credentials.Certificate(
# #             os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
# #         )
# #         firebase_admin.initialize_app(cred)
# #     else:
# #         logger.info("Initializing Firebase with GCP default credentials")
# #         firebase_admin.initialize_app()
#
# def init_firebase():
#     if firebase_admin._apps:
#         return
#
#     logger.info("Initializing Firebase with service account credentials")
#     firebase_admin.initialize_app()

import os
import json
import logging
from firebase_admin import credentials
import firebase_admin

logger = logging.getLogger(__name__)

def init_firebase():
    if firebase_admin._apps:
        return

    firebase_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    firebase_json_path = os.getenv("FIREBASE_CREDENTIALS_JSON_PATH")

    print(f'test001 {firebase_json}')

    # 🔥 JSON이 실제 JSON이 아닐 경우 무효화
    if firebase_json:
        try:
            print('test002')
            json.loads(firebase_json)
        except json.JSONDecodeError:
            logger.warning(
                "FIREBASE_CREDENTIALS_JSON is not valid JSON. Ignoring it."
            )
            firebase_json = None

    print('test003')
    # 🔹 로컬 fallback: path → json string
    if not firebase_json and firebase_json_path:
        logger.info("Loading Firebase credentials from JSON file path")
        with open(firebase_json_path, "r", encoding="utf-8") as f:
            firebase_json = f.read()

    if firebase_json:
        logger.info("Using Firebase credentials from environment variable")
        cred_dict = json.loads(firebase_json)
        logger.info(f"Firebase project: {cred_dict.get('project_id')}")
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    else:
        logger.info("Using default credentials")
        firebase_admin.initialize_app()

    print('test004')
    app = firebase_admin.get_app()
    logger.info(f"✅ Firebase initialized with project: {app.project_id}")

from firebase_admin import messaging


def send_push_message(
    *,
    token: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> None:
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(
            title=title,
            body=body,
            image="https://firebasestorage.googleapis.com/v0/b/lattui-auth.firebasestorage.app/o/FCMImages%2FIcon-192.png?alt=media&token=a47b85ee-1ade-4406-8c94-7310e48d747a",
        ),
        data=data or {},
    )

    messaging.send(message)