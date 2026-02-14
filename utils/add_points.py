import requests

from flask import session


API_URL = "http://158.160.104.26:9001/api"


def add_points(amount: int) -> int:
    user_id = session.get("user_id")

    if not user_id:
        raise Exception("Не записан user_id в сессию.")

    response = requests.post(
        f"{API_URL}/users/{user_id}/points", json={"amount": amount}
    )

    if response.status_code != 200:
        raise Exception(f"Ошибка API: {response.text}")

    data = response.json()
    points = data.get("newTotalPoints")

    if not points:
        raise Exception("Произошла ошибка!")

    return points