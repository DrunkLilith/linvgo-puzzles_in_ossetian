import os

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix

from data._all_models import db, User, Riddle
from utils import api

DATABASE_PATH = os.path.abspath("db/puzzles.db")


# Создание экземпляра приложения
def main():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "your_secret_key")  # Ключ для работы с сессиями
    path_base = os.environ.get("GAME_PATH_BASE", "").rstrip("/")
    app.config["APPLICATION_ROOT"] = path_base or "/"
    app.config["SESSION_COOKIE_PATH"] = path_base or "/"
    app.config["SESSION_COOKIE_NAME"] = os.environ.get(
        "GAME_COOKIE_NAME", "lingvogameos_puzzles_session"
    )
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

    # Настройка пути к базе данных
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Инициализация базы данных
    db.init_app(app)

    return app


app = main()

ossetian_alphabet = [
    "а",
    "æ",
    "б",
    "г",
    "гъ",
    "д",
    "дж",
    "дз",
    "ж",
    "з",
    "и",
    "й",
    "н",
    "о",
    "р",
    "с",
    "у",
    "ф",
    "х",
    "хъ",
    "ы",
    "-",
]

# Создание таблиц и заполнение ребусов при первом запуске
with app.app_context():
    try:
        # Проверяем, существует ли папка db/
        db_dir = os.path.dirname(DATABASE_PATH)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)  # Создаем папку db/, если её нет
        # Создаем таблицы
        db.create_all()
        # Проверяем, есть ли уже ребусы в базе данных
        if not Riddle.query.first():
            # хранение картинок, ответов, подсказок на ребусы
            rebuses = [
                {
                    "image": "rebus1.png",
                    "answer": "хæрисджын",
                    "hints": "Первая буква 'х', В слове 8 букв, æ дж",
                },
                {
                    "image": "rebus2.png",
                    "answer": "бирæгъзæнг",
                    "hints": "Первая буква 'б', В слове 9 букв, æ гъ",
                },
                {
                    "image": "rebus3.png",
                    "answer": "фыййагдон",
                    "hints": "Первая буква 'ф', В слове 9 букв, ы й",
                },
                {
                    "image": "rebus4.png",
                    "answer": "сындзыхъæу",
                    "hints": "Первая буква 'с', В слове 8 букв, дз хъ",
                },
                {
                    "image": "rebus5.png",
                    "answer": "дур-дур",
                    "hints": "Первая буква 'д', В слове 7 букв, д",
                },
            ]
            for r in rebuses:
                new_riddle = Riddle(
                    image=r["image"], answer=r["answer"], hints=r["hints"]
                )
                db.session.add(new_riddle)
            db.session.commit()
    except Exception as e:
        print(f"Ошибка при создании базы данных: {e}")


# Маршруты
# главная страница
@app.route("/")
@app.route("/start")
def index():
    # игровая сессия портала: iframe передаёт ?session=<id>
    if "game_session_id" not in session:
        session["game_session_id"] = None
    previous_session_id = session.get("game_session_id")
    api.get_game_session_id()

    # Новый запуск из портала получает новый одноразовый session id. Flask-cookie
    # при этом может сохраниться от прошлой игры, поэтому начинаем прохождение
    # заново и разрешаем одно новое итоговое начисление.
    if (
        session.get("game_session_id")
        and session.get("game_session_id") != previous_session_id
    ):
        session["score"] = 0
        session["solved_rebuses"] = []
        session["current_rebus_id"] = 1
        session.pop("portal_score_submitted", None)
        session.pop("portal_total_points", None)
        for key in list(session):
            if key.startswith("hints_left_"):
                session.pop(key, None)
    return render_template("index.html")


# страница правил
@app.route("/rules")
def rules():
    return render_template("rules.html")


# войти (через API портала Рудзынг.рф)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        try:
            user_id = api.login(email, password)
            # имя для отображения и локального рейтинга
            session["username"] = email
            session.pop("score", None)
            session.pop("solved_rebuses", None)
            return redirect(url_for("game"))
        except api.ApiError as e:
            flash(str(e), "danger")
    return render_template("login.html")


# зарегистрироваться (на портале)
@app.route("/register", methods=["GET", "POST"])
def register():
    portal_url = os.environ.get("PORTAL_URL", "https://рудзынг.рф").rstrip("/")
    return redirect(f"{portal_url}/Account/Register")


# выйти
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# сама игра
@app.route("/game", methods=["GET", "POST"])
def game():
    # Инициализация данных для гостя или загрузка данных пользователя
    if "username" not in session:
        session["username"] = "Guest"
        session["score"] = session.get("score", 0)
        session["solved_rebuses"] = session.get("solved_rebuses", [])
        session["current_rebus_id"] = session.get(
            "current_rebus_id", 1
        )  # Инициализация текущего ID ребуса

    # Получаем текущий ID ребуса из параметров запроса или сессии
    current_rebus_id = int(request.args.get("rebus_id", session["current_rebus_id"]))
    session["current_rebus_id"] = current_rebus_id

    # Проверка на уже решенные ребусы
    while str(current_rebus_id) in session["solved_rebuses"]:
        current_rebus_id += 1

    session["current_rebus_id"] = current_rebus_id

    rebuses = Riddle.query.all()
    # отображение текущего ребуса
    current_rebus = next((r for r in rebuses if r.id == current_rebus_id), None)

    # Если все ребусы решены
    if current_rebus is None:
        return redirect(url_for("success"))
    # подсказок осталось

    hints_left_key = f"hints_left_{current_rebus_id}"
    # сколько подсказок осталось
    hints_left = session.get(hints_left_key, 3)

    # при вводе ответа
    if request.method == "POST":
        action = request.form.get("action")
        # при нажатии проверить ответ
        if action == "check_answer":
            user_answer = request.form["answer"].strip()
            if user_answer == current_rebus.answer:
                # если ребус не был решен ранее
                if str(current_rebus_id) not in session["solved_rebuses"]:
                    new_score = min(session["score"] + 20, 100)
                    session["score"] = new_score
                    session["solved_rebuses"].append(str(current_rebus_id))
                    flash("Правильно!", "success")
                current_rebus_id += 1
                session["current_rebus_id"] = current_rebus_id
                # Переход к следующему нерешенному ребусу
                while str(current_rebus_id) in session["solved_rebuses"]:
                    current_rebus_id += 1
                session["current_rebus_id"] = current_rebus_id
                return redirect(url_for("game", rebus_id=current_rebus_id))
            else:
                flash("Неправильно. Попробуйте еще раз.", "danger")

        # при нажатии на подсказку
        elif action == "show_hint":
            if hints_left > 0:
                hints_left -= 1
                session[hints_left_key] = hints_left
                # отображение
                flash(f"Подсказка: {current_rebus.hints}", "info")
            else:
                # если закончились
                flash("У вас закончились подсказки для этого ребуса!", "warning")

    return render_template(
        "game.html",
        rebus=current_rebus,
        score=session["score"],
        ossetian_alphabet=ossetian_alphabet,
        hints_left=hints_left,
    )


# рейтинг
@app.route("/rating")
def rating():
    ratings = User.query.order_by(User.score.desc()).all()
    return render_template("rating.html", ratings=ratings)


# при решении всех ребусов
@app.route("/success")
def success():
    # API принимает ровно одно начисление на игровую сессию. Поэтому отправляем
    # накопленный результат только после прохождения всех загадок, а не после
    # каждой из них. Флаг защищает от повторной отправки при обновлении страницы.
    total = session.get("score")
    if (
        session.get("game_session_id")
        and total
        and not session.get("portal_score_submitted")
    ):
        try:
            total = api.add_points(int(total))
            session["portal_score_submitted"] = True
            session["portal_total_points"] = total
        except api.ApiError as e:
            print(f"Не удалось начислить итоговые баллы: {e}")
    elif session.get("portal_total_points") is not None:
        total = session["portal_total_points"]

    # если игра открыта вне портала гостем — предлагаем зарегистрироваться
    if "user_id" not in session and not session.get("game_session_id"):
        return render_template("success.html", show_register_prompt=True)

    return render_template("success.html", total=total)


@app.route("/register_prompt/<int:rebus_id>", methods=["GET", "POST"])
def register_prompt(rebus_id):
    if request.method == "POST":
        action = request.form.get("action")
        if action == "continue_as_guest":
            # Продолжаем игру с того же места
            print(
                f"Redirecting to game with rebus_id={rebus_id}"
            )  # Отладочная информация
            return redirect(url_for("game", rebus_id=rebus_id))
    return render_template("register_prompt.html", rebus_id=rebus_id)


if __name__ == "__main__":
    app.run()
