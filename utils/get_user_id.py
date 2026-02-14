from flask import session
import requests


API_URL = "http://158.160.104.26:9001/api"


def get_user_id(email, password):

    if not (email and password):
        raise Exception("Неправильные данные!")

    user_data = {"email": email, "password": password}

    response = requests.post(f"{API_URL}/account/login", json=user_data)

    if response.status_code != 200:
        raise Exception(f"Ошибка API: {response.text}")

    data = response.json()
    user_id = None

    if isinstance(data, str):
        user_id = data
    elif isinstance(data, dict):
        user_id = data.get("userId")

    if not user_id:
        raise Exception("Не получен ID пользователя")
    session["user_id"] = user_id

    return user_id
