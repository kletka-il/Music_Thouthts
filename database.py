import sqlite3

import os

import re

import random

from werkzeug.security import generate_password_hash

from datetime import datetime, timedelta



DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_thoughts.db")





def get_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")

    return conn





SCHEMA = "CREATE TABLE IF NOT EXISTS users (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    username TEXT UNIQUE NOT NULL,\n    email TEXT UNIQUE NOT NULL,\n    password_hash TEXT NOT NULL,\n    role TEXT NOT NULL DEFAULT 'viewer',\n    bio TEXT DEFAULT '',\n    avatar_emoji TEXT DEFAULT '🎵',\n    theme TEXT DEFAULT 'dark',\n    favorite_genre TEXT DEFAULT '',\n    spotify_link TEXT DEFAULT '',\n    listening_now TEXT DEFAULT '',\n    is_banned INTEGER NOT NULL DEFAULT 0,\n    ban_reason TEXT DEFAULT '',\n    created_at TEXT NOT NULL,\n    last_login TEXT,\n    streak_days INTEGER NOT NULL DEFAULT 0,\n    last_visit_day TEXT\n);\n\nCREATE TABLE IF NOT EXISTS reviews (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    author_id INTEGER NOT NULL,\n    artist TEXT NOT NULL,\n    title TEXT NOT NULL,\n    genre TEXT DEFAULT '',\n    year INTEGER,\n    cover_url TEXT DEFAULT '',\n    listen_url TEXT DEFAULT '',\n    body TEXT NOT NULL,\n    score INTEGER NOT NULL DEFAULT 5,\n    mood TEXT DEFAULT '',\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    is_featured INTEGER NOT NULL DEFAULT 0,\n    is_draft INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL,\n    updated_at TEXT NOT NULL,\n    views INTEGER NOT NULL DEFAULT 0,\n    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS comments (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    review_id INTEGER NOT NULL,\n    author_id INTEGER NOT NULL,\n    parent_id INTEGER,\n    body TEXT NOT NULL,\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL,\n    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE,\n    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,\n    FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS ratings (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    review_id INTEGER NOT NULL,\n    user_id INTEGER NOT NULL,\n    value INTEGER NOT NULL,\n    created_at TEXT NOT NULL,\n    UNIQUE(review_id, user_id),\n    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE,\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS comment_ratings (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    comment_id INTEGER NOT NULL,\n    user_id INTEGER NOT NULL,\n    value INTEGER NOT NULL,\n    created_at TEXT NOT NULL,\n    UNIQUE(comment_id, user_id),\n    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS reports (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    reporter_id INTEGER NOT NULL,\n    target_type TEXT NOT NULL,\n    target_id INTEGER NOT NULL,\n    reason TEXT NOT NULL,\n    status TEXT NOT NULL DEFAULT 'open',\n    handler_id INTEGER,\n    resolution TEXT DEFAULT '',\n    created_at TEXT NOT NULL,\n    resolved_at TEXT,\n    FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS mod_log (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    moderator_id INTEGER NOT NULL,\n    action TEXT NOT NULL,\n    details TEXT DEFAULT '',\n    created_at TEXT NOT NULL,\n    FOREIGN KEY (moderator_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS guestbook (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    author_name TEXT NOT NULL,\n    body TEXT NOT NULL,\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS settings (\n    key TEXT PRIMARY KEY,\n    value TEXT NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS banned_words (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    word TEXT UNIQUE NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS site_stats (\n    key TEXT PRIMARY KEY,\n    value INTEGER NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS tags (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    name TEXT UNIQUE NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS review_tags (\n    review_id INTEGER NOT NULL,\n    tag_id INTEGER NOT NULL,\n    PRIMARY KEY (review_id, tag_id),\n    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE,\n    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS follows (\n    follower_id INTEGER NOT NULL,\n    followee_id INTEGER NOT NULL,\n    created_at TEXT NOT NULL,\n    PRIMARY KEY (follower_id, followee_id),\n    FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,\n    FOREIGN KEY (followee_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS bookmarks (\n    user_id INTEGER NOT NULL,\n    review_id INTEGER NOT NULL,\n    created_at TEXT NOT NULL,\n    PRIMARY KEY (user_id, review_id),\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,\n    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS notifications (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    user_id INTEGER NOT NULL,\n    kind TEXT NOT NULL,\n    body TEXT NOT NULL,\n    link TEXT DEFAULT '',\n    is_read INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL,\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS achievements (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    user_id INTEGER NOT NULL,\n    code TEXT NOT NULL,\n    awarded_at TEXT NOT NULL,\n    UNIQUE(user_id, code),\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS playlists (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    owner_id INTEGER NOT NULL,\n    title TEXT NOT NULL,\n    description TEXT DEFAULT '',\n    cover_emoji TEXT DEFAULT '🎶',\n    is_public INTEGER NOT NULL DEFAULT 1,\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL,\n    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS playlist_items (\n    playlist_id INTEGER NOT NULL,\n    review_id INTEGER NOT NULL,\n    position INTEGER NOT NULL DEFAULT 0,\n    note TEXT DEFAULT '',\n    PRIMARY KEY (playlist_id, review_id),\n    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,\n    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS song_of_day (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    review_id INTEGER NOT NULL,\n    note TEXT DEFAULT '',\n    set_at TEXT NOT NULL,\n    set_by INTEGER,\n    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS lyrics_quotes (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    text TEXT NOT NULL,\n    artist TEXT DEFAULT '',\n    song TEXT DEFAULT '',\n    submitted_by INTEGER,\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS events (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    title TEXT NOT NULL,\n    description TEXT DEFAULT '',\n    city TEXT DEFAULT '',\n    venue TEXT DEFAULT '',\n    starts_at TEXT NOT NULL,\n    link TEXT DEFAULT '',\n    cover_emoji TEXT DEFAULT '🎤',\n    created_by INTEGER,\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS event_attendees (\n    event_id INTEGER NOT NULL,\n    user_id INTEGER NOT NULL,\n    PRIMARY KEY (event_id, user_id),\n    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS polls (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    question TEXT NOT NULL,\n    is_closed INTEGER NOT NULL DEFAULT 0,\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    created_by INTEGER,\n    created_at TEXT NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS poll_options (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    poll_id INTEGER NOT NULL,\n    text TEXT NOT NULL,\n    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS poll_votes (\n    poll_id INTEGER NOT NULL,\n    option_id INTEGER NOT NULL,\n    user_id INTEGER NOT NULL,\n    created_at TEXT NOT NULL,\n    PRIMARY KEY (poll_id, user_id),\n    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,\n    FOREIGN KEY (option_id) REFERENCES poll_options(id) ON DELETE CASCADE,\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS challenges (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    title TEXT NOT NULL,\n    description TEXT DEFAULT '',\n    starts_at TEXT NOT NULL,\n    ends_at TEXT NOT NULL,\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    created_by INTEGER,\n    created_at TEXT NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS challenge_submissions (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    challenge_id INTEGER NOT NULL,\n    user_id INTEGER NOT NULL,\n    review_id INTEGER,\n    text TEXT DEFAULT '',\n    created_at TEXT NOT NULL,\n    UNIQUE(challenge_id, user_id),\n    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,\n    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE SET NULL\n);\n\nCREATE TABLE IF NOT EXISTS listening_log (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    user_id INTEGER NOT NULL,\n    artist TEXT NOT NULL,\n    title TEXT DEFAULT '',\n    note TEXT DEFAULT '',\n    mood TEXT DEFAULT '',\n    rating INTEGER DEFAULT 0,\n    created_at TEXT NOT NULL,\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS shoutouts (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    profile_user_id INTEGER NOT NULL,\n    author_id INTEGER NOT NULL,\n    body TEXT NOT NULL,\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL,\n    FOREIGN KEY (profile_user_id) REFERENCES users(id) ON DELETE CASCADE,\n    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS dm_messages (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    from_id INTEGER NOT NULL,\n    to_id INTEGER NOT NULL,\n    body TEXT NOT NULL,\n    is_read INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL,\n    FOREIGN KEY (from_id) REFERENCES users(id) ON DELETE CASCADE,\n    FOREIGN KEY (to_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS quiz_questions (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    question TEXT NOT NULL,\n    options TEXT NOT NULL,\n    correct INTEGER NOT NULL,\n    explanation TEXT DEFAULT '',\n    is_hidden INTEGER NOT NULL DEFAULT 0,\n    created_at TEXT NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS quiz_attempts (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    user_id INTEGER NOT NULL,\n    score INTEGER NOT NULL,\n    total INTEGER NOT NULL,\n    created_at TEXT NOT NULL,\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE TABLE IF NOT EXISTS track_scores (\n    review_id INTEGER NOT NULL,\n    user_id INTEGER NOT NULL,\n    value INTEGER NOT NULL CHECK(value BETWEEN 1 AND 10),\n    created_at TEXT NOT NULL,\n    PRIMARY KEY (review_id, user_id),\n    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE,\n    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n);\n\nCREATE INDEX IF NOT EXISTS idx_track_scores_review ON track_scores(review_id);\n\nCREATE INDEX IF NOT EXISTS idx_reviews_author ON reviews(author_id);\nCREATE INDEX IF NOT EXISTS idx_reviews_genre ON reviews(genre);\nCREATE INDEX IF NOT EXISTS idx_comments_review ON comments(review_id);\nCREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);\nCREATE INDEX IF NOT EXISTS idx_dm_pair ON dm_messages(from_id, to_id);\nCREATE INDEX IF NOT EXISTS idx_listening_user ON listening_log(user_id);\n"







ACHIEVEMENT_CATALOG = {

    "first_review":   ("Первая рецензия", "Опубликована первая рецензия", "🎤"),

    "five_reviews":   ("Серьёзный автор", "5 опубликованных рецензий", "✍️"),

    "ten_reviews":    ("Критик", "10 рецензий — стабильный голос сообщества", "📚"),

    "twenty_reviews": ("Эрудит", "20 рецензий — настоящий знаток", "🎓"),

    "first_comment":  ("Первое слово", "Оставлен первый комментарий", "💬"),

    "popular_review": ("Хайп", "Рецензия набрала 10+ голосов", "🔥"),

    "viral_review":   ("Вирус", "Рецензия набрала 25+ голосов", "🌪"),

    "veteran":        ("Старожил", "На сайте больше месяца", "🏛"),

    "follower_5":     ("Авторитет", "5+ подписчиков", "👥"),

    "follower_25":    ("Голос сцены", "25+ подписчиков", "🎙"),

    "moderator":      ("Хранитель", "Назначен модератором", "🛡"),

    "playlist_maker": ("Куратор", "Создан первый плейлист", "🎚"),

    "diary_keeper":   ("Дневниковед", "10 записей в дневнике прослушивания", "📓"),

    "challenger":     ("Бросает вызов", "Принят музыкальный челлендж", "🥇"),

    "quiz_master":    ("Эрудит-знаток", "Викторина на 80%+ правильных", "🧠"),

    "streak_7":       ("Неделя в строю", "7 дней подряд на сайте", "📅"),

    "streak_30":      ("Меломан-марафонец", "30 дней подряд на сайте", "🏃"),

    "social_bee":     ("Душа сообщества", "50+ комментариев", "🐝"),

    "lyric_lover":    ("Цитатник", "Добавлена цитата из песни", "📜"),

    "event_goer":     ("На концерте", "Записался на афишное событие", "🎫"),

}





NOTIF_KIND_RU = {

    "new_review":   "Новая рецензия",

    "comment":      "Комментарий",

    "reply":        "Ответ",

    "rating":       "Оценка",

    "follow":       "Подписка",

    "achievement":  "Достижение",

    "role":         "Роль",

    "dm":           "Личное сообщение",

    "shoutout":     "Запись на стене",

    "challenge":    "Челлендж",

    "event":        "Событие",

    "poll":         "Опрос",

    "song_of_day":  "Альбом дня",

    "system":       "Сообщение системы",

}





ROLE_RU = {

    "viewer":    "слушатель",

    "reviewer":  "рецензент",

    "moderator": "модератор",

}





MOOD_OPTIONS = [

    ("dreamy",    "🌙 мечтательное"),

    ("energetic", "⚡ заряжающее"),

    ("melancholy","🌧 меланхоличное"),

    ("party",     "🎉 танцевальное"),

    ("focus",     "🎧 для работы"),

    ("road",      "🚗 в дорогу"),

    ("nostalgia", "📼 ностальгия"),

    ("rebel",     "🤘 бунтарское"),

    ("calm",      "🌿 спокойное"),

]



MOOD_LABELS = dict(MOOD_OPTIONS)





def init_db():

    conn = get_db()

    conn.executescript(SCHEMA)

    conn.commit()



    now = datetime.utcnow().isoformat()



    if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] == 0:

        seed_users = [

            ("Админ_Иваныч", "admin@music-thoughts.ru", "admin1995", "moderator",

             "Главный модератор. Слежу за порядком и атмосферой.", "👑"),

            ("RetroFan2003", "retro@music-thoughts.ru", "windows98", "moderator",

             "Модератор. Винил, кассеты, MIDI — моя стихия.", "💿"),

            ("DJ_Sovetov", "dj@music-thoughts.ru", "kassetnik", "moderator",

             "Модератор. Микширую звуки и порядок.", "🎚️"),

            ("Рецензент_Котов", "kotov@music-thoughts.ru", "review123", "reviewer",

             "Пишу длинные рецензии на отечественную сцену.", "🎼"),

            ("Лена_Бит", "lena@music-thoughts.ru", "lena12345", "reviewer",

             "Электроника, IDM, новая волна.", "🎹"),

            ("Слушатель_Петров", "petrov@music-thoughts.ru", "listen123", "viewer",

             "Слушаю всё подряд. Комментирую много.", "🎧"),

        ]

        for username, email, password, role, bio, emoji in seed_users:

            conn.execute(

                "INSERT INTO users(username,email,password_hash,role,bio,avatar_emoji,created_at) "

                "VALUES (?,?,?,?,?,?,?)",

                (username, email, generate_password_hash(password), role, bio, emoji, now),

            )



    if conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"] == 0:

        kotov = conn.execute("SELECT id FROM users WHERE username='Рецензент_Котов'").fetchone()["id"]

        lena = conn.execute("SELECT id FROM users WHERE username='Лена_Бит'").fetchone()["id"]

        admin = conn.execute("SELECT id FROM users WHERE username='Админ_Иваныч'").fetchone()["id"]



        def yt(q):

            return "https://www.youtube.com/results?search_query=" + q.replace(" ", "+")



        

        seed_reviews = [

            (kotov, "Гражданская оборона", "Всё идёт по плану", "Панк-рок", 1989,

             "Альбом-икона. Сырой звук, революционные тексты, плотный драйв. "

             "Слушать обязательно — лучше всего на стареньком магнитофоне.", 10, 1, "rebel",

             "панк, классика, советский андеграунд",

             yt("Гражданская Оборона Всё идёт по плану")),

            (kotov, "Кино", "Группа крови", "Пост-панк", 1988,

             "Цой жив. Каждый трек — манифест поколения. Гитарные риффы простые, "

             "но врезаются в память навсегда.", 10, 1, "energetic",

             "ленинградский рок, классика",

             yt("Кино Группа крови альбом")),

            (kotov, "Аквариум", "Радио Африка", "Рок", 1983,

             "Магнитоальбом эпохи. БГ в лучшей форме. Атмосферная пластинка для долгих вечеров.",

             9, 0, "dreamy", "рок, эзотерика, магнитоальбом",

             yt("Аквариум Радио Африка")),

            (kotov, "Наутилус Помпилиус", "Разлука", "Рок", 1986,

             "Свердловский рок 80-х в чистом виде. «Скованные одной цепью» — гимн поколения.",

             9, 1, "melancholy", "рок, свердловск",

             yt("Наутилус Помпилиус Разлука альбом")),

            (kotov, "ДДТ", "Я получил эту роль", "Рок", 1988,

             "Шевчук — голос совести русского рока. Тексты бьют точно в нерв.",

             9, 0, "rebel", "рок, бард",

             yt("ДДТ Я получил эту роль")),

            (kotov, "Алиса", "BlokAda", "Рок", 1987,

             "Кинчев в самой бунтарской форме. Гитарная стена и манифесты.",

             8, 0, "rebel", "рок, ленинград",

             yt("Алиса БлокАда альбом")),

            (kotov, "Чайф", "Не беда", "Рок", 1991,

             "Уральский рок-н-ролл с человеческим лицом. Шахрин знает, как говорить просто.",

             8, 0, "energetic", "рок, урал",

             yt("Чайф Не беда")),

            (kotov, "Сплин", "Гранатовый альбом", "Рок", 1998,

             "Васильев на пике. Лирика, мелодия, нерв 90-х. «Орбит без сахара» — манифест эпохи.",

             10, 1, "melancholy", "рок, 90-е",

             yt("Сплин Гранатовый альбом")),

            (kotov, "Земфира", "Прости меня моя любовь", "Рок", 2000,

             "Самый цельный альбом Земфиры. Каждая песня — попадание в нерв поколения.",

             10, 1, "melancholy", "рок, поп-рок",

             yt("Земфира Прости меня моя любовь альбом")),

            (kotov, "Мумий Тролль", "Морская", "Рок", 1997,

             "Лагутенко изобрёл новый звук. Дальневосточный рок-н-ролл с эротическим подтекстом.",

             9, 0, "dreamy", "рок, поп-рок",

             yt("Мумий Тролль Морская альбом")),

            (kotov, "Би-2", "Иномарки", "Рок", 2001,

             "Альбом, который сделал Би-2 главной рок-группой нулевых. «Полковнику никто не пишет» — классика.",

             8, 0, "energetic", "рок, поп-рок",

             yt("Би-2 Иномарки альбом")),



            (lena, "Молчат Дома", "Этажи", "Пост-панк", 2018,

             "Современная классика пост-панка. Минск выдал альбом, который оценили во всём мире.",

             9, 1, "melancholy", "пост-панк, синтезаторы, новая волна",

             yt("Молчат Дома Этажи альбом")),

            (lena, "Молчат Дома", "С крыш наших домов", "Пост-панк", 2017,

             "Дебют, задавший формулу. Холодные синты, басовая стена, голос как из подвала.",

             8, 0, "melancholy", "пост-панк",

             yt("Молчат Дома С крыш наших домов")),

            (lena, "Pompeya", "Real", "Synth-pop", 2012,

             "Чистый, лёгкий синтипоп с английским вокалом — но всё равно наша сцена.",

             8, 0, "party", "синти-поп, инди",

             yt("Pompeya Real album")),

            (lena, "СБПЧ", "Молодость", "Инди-поп", 2014,

             "Светлый альбом про взросление. Песни, которые хочется слушать летом в наушниках.",

             8, 0, "dreamy", "инди, лето",

             yt("СБПЧ Молодость альбом")),

            (lena, "АИГЕЛ", "Татарин", "Электроника", 2017,

             "Айгель Гайсина и Илья Барамия — манифест татарской электроники.",

             9, 1, "rebel", "электроника, фолк, татарский",

             yt("АИГЕЛ Татарин")),

            (lena, "ИЗДЕБСКИЙ", "Sigh", "IDM", 2020,

             "Тонкий ambient/IDM альбом. Для долгих ночных прослушиваний.",

             8, 0, "focus", "idm, эмбиент",

             yt("Издебский Sigh")),

            (lena, "On-The-Go", "Hindsight", "Инди-рок", 2014,

             "Питерский инди-рок с английским вокалом. Драйвовый, мелодичный, чистый.",

             8, 0, "energetic", "инди, рок",

             yt("On-The-Go Hindsight")),

            (lena, "Tesla Boy", "The Universe Made Of Darkness", "Synth-pop", 2010,

             "Эталонный российский синти-поп. Романтика 80-х в современной обёртке.",

             8, 0, "dreamy", "синти-поп, ретро",

             yt("Tesla Boy The Universe Made Of Darkness")),

            (lena, "Lucidvox", "We Are", "Психоделик-рок", 2019,

             "Девичий московский квартет. Психоделия, фолк-мотивы, мощная подача.",

             9, 1, "rebel", "психоделика, рок",

             yt("Lucidvox We Are album")),

            (lena, "Shortparis", "Так закалялась сталь", "Пост-панк", 2017,

             "Театральный, телесный пост-панк. Концерты Shortparis — событие.",

             9, 1, "melancholy", "пост-панк, экспериментальное",

             yt("Shortparis Так закалялась сталь")),

            (lena, "Pixelord", "Boom Box", "Электроника", 2013,

             "Российская танцевальная электроника. Коллаборации, бас, цвет.",

             8, 0, "party", "электроника, басс",

             yt("Pixelord Boom Box")),



            (admin, "Звуки Му", "Простые вещи", "Авангард", 1988,

             "Мамонов в лучшей форме. Странный, тревожный, гениальный альбом.",

             9, 0, "rebel", "авангард, советский андеграунд",

             yt("Звуки Му Простые вещи")),

            (admin, "Кино", "Звезда по имени Солнце", "Рок", 1989,

             "Последний прижизненный альбом Цоя. Каждая строчка — на разрыв.",

             10, 1, "melancholy", "рок, классика",

             yt("Кино Звезда по имени Солнце альбом")),

            (admin, "Аукцыон", "Птица", "Арт-рок", 1993,

             "Фёдоров и компания. Шамански, энергично, ни на что не похоже.",

             9, 0, "dreamy", "арт-рок, экспериментальное",

             yt("Аукцыон Птица альбом")),

            (admin, "Мираж", "Звёзды нас ждут", "Дискотека", 1987,

             "Главная советская поп-машина. Синтезаторы, ритм, ностальгия.",

             7, 0, "party", "поп, дискотека, 80-е",

             yt("Мираж Звёзды нас ждут")),

            (admin, "Технология", "Всё, что ты хочешь", "Synth-pop", 1991,

             "Русская «Depeche Mode эра». Холодные синты и мрачные тексты.",

             8, 0, "melancholy", "синти-поп, 90-е",

             yt("Технология Всё что ты хочешь альбом")),

            (admin, "Каста", "Громче воды, выше травы", "Хип-хоп", 2002,

             "Ростовский хип-хоп взорвал нулевые. Тексты до сих пор актуальны.",

             9, 1, "energetic", "хип-хоп, ростов",

             yt("Каста Громче воды выше травы")),

            (admin, "Касабиан Стэнс", "Прохожий", "Инди", 2021,

             "Молодая сцена. Лиричный инди с гитарным звуком.",

             7, 0, "dreamy", "инди, новое",

             yt("Касабиан Стэнс Прохожий")),

            (admin, "Дельфин", "Глубина резкости", "Электроника", 2004,

             "Дельфин ушёл от рэпа в холодную электронику. Альбом — медитация.",

             9, 0, "focus", "электроника, лирика",

             yt("Дельфин Глубина резкости")),

        ]

        review_ids = []

        for author, artist, title, genre, year, body, score, featured, mood, tags_str, listen in seed_reviews:

            cur = conn.execute(

                "INSERT INTO reviews(author_id,artist,title,genre,year,body,score,is_featured,mood,"

                "listen_url,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",

                (author, artist, title, genre, year, body, score, featured, mood, listen, now, now),

            )

            rid = cur.lastrowid

            review_ids.append(rid)

            for tname in [t.strip() for t in tags_str.split(",") if t.strip()]:

                conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tname,))

                tid = conn.execute("SELECT id FROM tags WHERE name=?", (tname,)).fetchone()["id"]

                conn.execute("INSERT OR IGNORE INTO review_tags(review_id, tag_id) VALUES (?,?)", (rid, tid))



        

        all_users = [r["id"] for r in conn.execute("SELECT id FROM users").fetchall()]

        rng = random.Random(42)

        for rid in review_ids:

            base = rng.randint(6, 10)

            for uid in all_users:

                if rng.random() < 0.55:

                    val = max(1, min(10, base + rng.randint(-2, 1)))

                    conn.execute(

                        "INSERT OR IGNORE INTO track_scores(review_id,user_id,value,created_at) "

                        "VALUES (?,?,?,?)",

                        (rid, uid, val, now),

                    )



        

        seed_playlists = [

            ("Русский рок: must listen", "🎸",

             "Десять записей, без которых разговор о русском роке невозможен.",

             [0, 1, 2, 3, 4, 7, 8, 9, 23, 24]),

            ("Холодная волна", "🌊",

             "Пост-панк, синти-поп и всё, что звучит как зимний вечер у окна.",

             [11, 12, 18, 20, 27]),

            ("Лето в наушниках", "☀️",

             "Лёгкие, светлые альбомы для прогулок и поездок.",

             [13, 14, 15, 18]),

            ("Электронные просторы", "🎛",

             "От IDM и эмбиента до танцевальных треков.",

             [16, 17, 22, 30, 32]),

            ("Авангард и эксперимент", "🌀",

             "Странное, неудобное, важное.",

             [21, 23, 25, 26]),

        ]

        for title, emoji, desc, idx_list in seed_playlists:

            cur = conn.execute(

                "INSERT INTO playlists(owner_id,title,description,cover_emoji,is_public,created_at) "

                "VALUES (?,?,?,?,1,?)",

                (admin, title, desc, emoji, now),

            )

            pid = cur.lastrowid

            for pos, idx in enumerate(idx_list):

                if idx < len(review_ids):

                    conn.execute(

                        "INSERT OR IGNORE INTO playlist_items(playlist_id,review_id,position,note) "

                        "VALUES (?,?,?,?)",

                        (pid, review_ids[idx], pos, ""),

                    )



    if conn.execute("SELECT COUNT(*) AS c FROM settings").fetchone()["c"] == 0:

        defaults = {

            "site_banner": "Music_Thoughts — площадка для разговора о музыке",

            "registration_open": "1",

            "guestbook_open": "1",

            "moderator_motd": "Будь объективен. Уважай авторов.",

            "site_tagline": "Рецензии. Голоса. Сообщество.",

            "site_quote": "«Музыка — это стенограмма эмоций.» — Лев Толстой",

        }

        for k, v in defaults.items():

            conn.execute("INSERT INTO settings(key,value) VALUES (?,?)", (k, v))



    if conn.execute("SELECT COUNT(*) AS c FROM banned_words").fetchone()["c"] == 0:

        for w in ["спам", "реклама", "scam"]:

            conn.execute("INSERT OR IGNORE INTO banned_words(word) VALUES (?)", (w,))



    if conn.execute("SELECT COUNT(*) AS c FROM site_stats").fetchone()["c"] == 0:

        conn.execute("INSERT INTO site_stats(key,value) VALUES ('visits', 0)")



    if conn.execute("SELECT COUNT(*) AS c FROM guestbook").fetchone()["c"] == 0:

        conn.execute(

            "INSERT INTO guestbook(author_name,body,created_at) VALUES (?,?,?)",

            ("Команда", "Привет! Это Music_Thoughts. Расскажите, что слушаете.", now),

        )



    if conn.execute("SELECT COUNT(*) AS c FROM lyrics_quotes").fetchone()["c"] == 0:

        seed_quotes = [

            ("Солнце моё, взгляни на меня — моя ладонь превратилась в кулак.", "Кино", "Звезда по имени Солнце"),

            ("Дальше действовать будем мы.", "Кино", "Дальше действовать будем мы"),

            ("Всё идёт по плану.", "Гражданская оборона", "Всё идёт по плану"),

            ("Город, которого нет.", "Игорь Корнелюк", "Город, которого нет"),

            ("Я хочу быть с тобой.", "Наутилус Помпилиус", "Я хочу быть с тобой"),

            ("Под небом голубым есть город золотой.", "Аквариум", "Город"),

            ("Пачка сигарет — и горит звезда.", "Кино", "Пачка сигарет"),

            ("Нам с тобой голубых небес навес.", "ДДТ", "Что такое осень"),

            ("Этажи горят, а ты молчишь.", "Молчат Дома", "Этажи"),

            ("Музыка нас связала.", "Мираж", "Музыка нас связала"),

        ]

        for text, artist, song in seed_quotes:

            conn.execute(

                "INSERT INTO lyrics_quotes(text,artist,song,created_at) VALUES (?,?,?,?)",

                (text, artist, song, now),

            )



    if conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"] == 0:

        future = datetime.utcnow() + timedelta(days=14)

        far = datetime.utcnow() + timedelta(days=45)

        conn.execute(

            "INSERT INTO events(title,description,city,venue,starts_at,cover_emoji,created_at) "

            "VALUES (?,?,?,?,?,?,?)",

            ("Вечер пост-панка", "Сборник местных групп. Бесплатный вход для участников сообщества.",

             "Москва", "ДК «Звук»", future.isoformat(), "🎸", now),

        )

        conn.execute(

            "INSERT INTO events(title,description,city,venue,starts_at,cover_emoji,created_at) "

            "VALUES (?,?,?,?,?,?,?)",

            ("Фестиваль электроники", "Большой open-air c IDM, техно и эмбиентом.",

             "Санкт-Петербург", "Парк «Севкабель»", far.isoformat(), "🎛", now),

        )



    if conn.execute("SELECT COUNT(*) AS c FROM polls").fetchone()["c"] == 0:

        cur = conn.execute(

            "INSERT INTO polls(question,created_at) VALUES (?,?)",

            ("Какой жанр сейчас слушаете чаще всего?", now),

        )

        pid = cur.lastrowid

        for opt in ["Рок / пост-панк", "Электроника / IDM", "Хип-хоп / рэп", "Фолк / эстрада", "Классическое"]:

            conn.execute("INSERT INTO poll_options(poll_id,text) VALUES (?,?)", (pid, opt))



    if conn.execute("SELECT COUNT(*) AS c FROM challenges").fetchone()["c"] == 0:

        start = datetime.utcnow().isoformat()

        end = (datetime.utcnow() + timedelta(days=7)).isoformat()

        conn.execute(

            "INSERT INTO challenges(title,description,starts_at,ends_at,created_at) "

            "VALUES (?,?,?,?,?)",

            ("Альбом, который изменил твоё лето",

             "Поделись альбомом, который сильнее всего ассоциируется у тебя с летом, и расскажи почему. "

             "Можно прикрепить ссылку на свою рецензию.",

             start, end, now),

        )



    if conn.execute("SELECT COUNT(*) AS c FROM quiz_questions").fetchone()["c"] == 0:

        seed_q = [

            ("В каком году вышел альбом «Группа крови» группы Кино?",

             "1986|1988|1990|1992", 1, "«Группа крови» — 1988 год."),

            ("Кто фронтмен группы «Гражданская оборона»?",

             "Виктор Цой|Егор Летов|Юрий Шевчук|Борис Гребенщиков", 1, "Егор Летов."),

            ("Какая группа исполнила «Город, которого нет»?",

             "Наутилус Помпилиус|Сплин|Игорь Корнелюк|Чайф", 2, "Игорь Корнелюк."),

            ("Из какой страны родом группа Молчат Дома?",

             "Россия|Беларусь|Украина|Латвия", 1, "Беларусь, Минск."),

            ("Кто пел «Под небом голубым есть город золотой»?",

             "Кино|Аквариум|ДДТ|Алиса", 1, "Аквариум, БГ."),

        ]

        for q, opts, c, expl in seed_q:

            conn.execute(

                "INSERT INTO quiz_questions(question,options,correct,explanation,created_at) "

                "VALUES (?,?,?,?,?)",

                (q, opts, c, expl, now),

            )



    

    if conn.execute("SELECT COUNT(*) AS c FROM song_of_day").fetchone()["c"] == 0:

        first = conn.execute(

            "SELECT id FROM reviews WHERE is_featured=1 LIMIT 1"

        ).fetchone()

        if first:

            conn.execute(

                "INSERT INTO song_of_day(review_id,note,set_at) VALUES (?,?,?)",

                (first["id"], "Стартовый выбор сообщества.", now),

            )



    conn.commit()

    conn.close()





def get_setting(key, default=""):

    conn = get_db()

    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()

    conn.close()

    return row["value"] if row else default





def set_setting(key, value):

    conn = get_db()

    conn.execute(

        "INSERT INTO settings(key,value) VALUES (?,?) "

        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",

        (key, value),

    )

    conn.commit()

    conn.close()





def increment_visits():

    conn = get_db()

    conn.execute("UPDATE site_stats SET value = value + 1 WHERE key='visits'")

    conn.commit()

    row = conn.execute("SELECT value FROM site_stats WHERE key='visits'").fetchone()

    conn.close()

    return row["value"] if row else 0





def get_visits():

    conn = get_db()

    row = conn.execute("SELECT value FROM site_stats WHERE key='visits'").fetchone()

    conn.close()

    return row["value"] if row else 0





def log_mod_action(moderator_id, action, details=""):

    conn = get_db()

    conn.execute(

        "INSERT INTO mod_log(moderator_id,action,details,created_at) VALUES (?,?,?,?)",

        (moderator_id, action, details, datetime.utcnow().isoformat()),

    )

    conn.commit()

    conn.close()





def filter_banned_words(text):

    conn = get_db()

    rows = conn.execute("SELECT word FROM banned_words").fetchall()

    conn.close()

    out = text or ""

    for r in rows:

        word = r["word"]

        if not word:

            continue

        out = re.sub(re.escape(word), "*" * len(word), out, flags=re.IGNORECASE)

    return out





def push_notification(user_id, kind, body, link=""):

    if not user_id:

        return

    conn = get_db()

    conn.execute(

        "INSERT INTO notifications(user_id,kind,body,link,created_at) VALUES (?,?,?,?,?)",

        (user_id, kind, body, link, datetime.utcnow().isoformat()),

    )

    conn.commit()

    conn.close()





def award_achievement(user_id, code):

    if code not in ACHIEVEMENT_CATALOG:

        return False

    conn = get_db()

    cur = conn.execute(

        "INSERT OR IGNORE INTO achievements(user_id,code,awarded_at) VALUES (?,?,?)",

        (user_id, code, datetime.utcnow().isoformat()),

    )

    awarded = cur.rowcount > 0

    conn.commit()

    conn.close()

    if awarded:

        title, desc, icon = ACHIEVEMENT_CATALOG[code]

        push_notification(user_id, "achievement", f"{icon} {title} — {desc}", link="/u/_self")

    return awarded





def recalc_achievements_for(user_id):

    conn = get_db()

    n_reviews = conn.execute(

        "SELECT COUNT(*) AS c FROM reviews WHERE author_id=? AND is_draft=0", (user_id,)

    ).fetchone()["c"]

    n_comments = conn.execute(

        "SELECT COUNT(*) AS c FROM comments WHERE author_id=?", (user_id,)

    ).fetchone()["c"]

    n_followers = conn.execute(

        "SELECT COUNT(*) AS c FROM follows WHERE followee_id=?", (user_id,)

    ).fetchone()["c"]

    n_playlists = conn.execute(

        "SELECT COUNT(*) AS c FROM playlists WHERE owner_id=?", (user_id,)

    ).fetchone()["c"]

    n_diary = conn.execute(

        "SELECT COUNT(*) AS c FROM listening_log WHERE user_id=?", (user_id,)

    ).fetchone()["c"]

    n_challenges = conn.execute(

        "SELECT COUNT(*) AS c FROM challenge_submissions WHERE user_id=?", (user_id,)

    ).fetchone()["c"]

    n_event = conn.execute(

        "SELECT COUNT(*) AS c FROM event_attendees WHERE user_id=?", (user_id,)

    ).fetchone()["c"]

    n_quotes = conn.execute(

        "SELECT COUNT(*) AS c FROM lyrics_quotes WHERE submitted_by=?", (user_id,)

    ).fetchone()["c"]

    quiz_best = conn.execute(

        "SELECT MAX(CAST(score AS REAL)/total) AS b FROM quiz_attempts WHERE user_id=? AND total>0",

        (user_id,),

    ).fetchone()

    user = conn.execute("SELECT role, created_at, streak_days FROM users WHERE id=?", (user_id,)).fetchone()

    pop = conn.execute(

        "SELECT MAX(net) AS m FROM ("

        "SELECT COALESCE(SUM(value),0) AS net FROM ratings "

        "WHERE review_id IN (SELECT id FROM reviews WHERE author_id=?) "

        "GROUP BY review_id)",

        (user_id,),

    ).fetchone()

    conn.close()

    if n_reviews >= 1:    award_achievement(user_id, "first_review")

    if n_reviews >= 5:    award_achievement(user_id, "five_reviews")

    if n_reviews >= 10:   award_achievement(user_id, "ten_reviews")

    if n_reviews >= 20:   award_achievement(user_id, "twenty_reviews")

    if n_comments >= 1:   award_achievement(user_id, "first_comment")

    if n_comments >= 50:  award_achievement(user_id, "social_bee")

    if n_followers >= 5:  award_achievement(user_id, "follower_5")

    if n_followers >= 25: award_achievement(user_id, "follower_25")

    if n_playlists >= 1:  award_achievement(user_id, "playlist_maker")

    if n_diary >= 10:     award_achievement(user_id, "diary_keeper")

    if n_challenges >= 1: award_achievement(user_id, "challenger")

    if n_event >= 1:      award_achievement(user_id, "event_goer")

    if n_quotes >= 1:     award_achievement(user_id, "lyric_lover")

    if quiz_best and quiz_best["b"] is not None and quiz_best["b"] >= 0.8:

        award_achievement(user_id, "quiz_master")

    if pop and pop["m"] and pop["m"] >= 10:

        award_achievement(user_id, "popular_review")

    if pop and pop["m"] and pop["m"] >= 25:

        award_achievement(user_id, "viral_review")

    if user and user["role"] == "moderator":

        award_achievement(user_id, "moderator")

    if user and user["streak_days"] and user["streak_days"] >= 7:

        award_achievement(user_id, "streak_7")

    if user and user["streak_days"] and user["streak_days"] >= 30:

        award_achievement(user_id, "streak_30")

    if user and user["created_at"]:

        try:

            ago = datetime.utcnow() - datetime.fromisoformat(user["created_at"])

            if ago.days >= 30:

                award_achievement(user_id, "veteran")

        except Exception:

            pass





def parse_tags(s):

    return [t.strip().lower() for t in (s or "").split(",") if t.strip()]





def set_review_tags(review_id, tag_names):

    conn = get_db()

    conn.execute("DELETE FROM review_tags WHERE review_id=?", (review_id,))

    for name in tag_names[:10]:

        if not name:

            continue

        conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))

        tid = conn.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()["id"]

        conn.execute("INSERT OR IGNORE INTO review_tags(review_id, tag_id) VALUES (?,?)",

                     (review_id, tid))

    conn.commit()

    conn.close()





def get_review_tags(review_id):

    conn = get_db()

    rows = conn.execute(

        "SELECT t.name FROM tags t JOIN review_tags rt ON rt.tag_id=t.id "

        "WHERE rt.review_id=? ORDER BY t.name",

        (review_id,),

    ).fetchall()

    conn.close()

    return [r["name"] for r in rows]





def _resolve_youtube_id(query, timeout=8):

                                                                              

    import urllib.request, urllib.parse

    try:

        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)

        req = urllib.request.Request(url, headers={

            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "

                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",

            "Accept-Language": "en-US,en;q=0.9",

        })

        html = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")

    except Exception:

        return None

    m = re.search(r'"videoId":"([\w-]{11})"', html)

    return m.group(1) if m else None





def resolve_listen_urls():

                                                                                            

    conn = get_db()

    rows = conn.execute(

        "SELECT id, artist, title, listen_url FROM reviews "

        "WHERE listen_url LIKE 'https://www.youtube.com/results?search_query=%'"

    ).fetchall()

    conn.close()

    fixed = 0

    for r in rows:

        q = f"{r['artist']} {r['title']}"

        vid = _resolve_youtube_id(q)

        if vid:

            new_url = f"https://www.youtube.com/watch?v={vid}"

            c = get_db()

            c.execute("UPDATE reviews SET listen_url=? WHERE id=?", (new_url, r["id"]))

            c.commit()

            c.close()

            fixed += 1

    return fixed





def detect_embed(url):

                                                                            

    if not url:

        return None

    u = url.strip()

    m = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)", u)

    if m:

        return f"https://www.youtube.com/embed/{m.group(1)}?rel=0"

    if "soundcloud.com" in u:

        return f"https://w.soundcloud.com/player/?url={u}&color=%23800020"

    if "open.spotify.com/" in u:

        path = u.split("open.spotify.com/")[-1].split("?")[0]

        return f"https://open.spotify.com/embed/{path}"

    return None





def update_streak(user_id):

                                                                      

    today = datetime.utcnow().strftime("%Y-%m-%d")

    conn = get_db()

    row = conn.execute(

        "SELECT streak_days, last_visit_day FROM users WHERE id=?", (user_id,)

    ).fetchone()

    if not row:

        conn.close()

        return 0

    streak = row["streak_days"] or 0

    last_day = row["last_visit_day"]

    if last_day == today:

        conn.close()

        return streak

    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    if last_day == yesterday:

        streak += 1

    else:

        streak = 1

    conn.execute(

        "UPDATE users SET streak_days=?, last_visit_day=? WHERE id=?",

        (streak, today, user_id),

    )

    conn.commit()

    conn.close()

    return streak





def get_song_of_day():

    conn = get_db()

    row = conn.execute(

        "SELECT s.*, r.artist, r.title, r.cover_url, r.score, r.id AS rid, "

        "u.username AS author "

        "FROM song_of_day s JOIN reviews r ON r.id=s.review_id "

        "JOIN users u ON u.id=r.author_id "

        "ORDER BY s.set_at DESC LIMIT 1"

    ).fetchone()

    conn.close()

    return row





def random_lyric_quote():

    conn = get_db()

    row = conn.execute(

        "SELECT * FROM lyrics_quotes WHERE is_hidden=0 ORDER BY RANDOM() LIMIT 1"

    ).fetchone()

    conn.close()

    return row





def get_recommendations_for(user_id, limit=5):

                                                                              

    conn = get_db()

    user = conn.execute("SELECT favorite_genre FROM users WHERE id=?", (user_id,)).fetchone()

    items = []

    seen_ids = set()

    if user and user["favorite_genre"]:

        rows = conn.execute(

            "SELECT r.*, u.username AS author, u.avatar_emoji AS author_emoji FROM reviews r "

            "JOIN users u ON u.id=r.author_id "

            "WHERE r.is_hidden=0 AND r.is_draft=0 AND LOWER(r.genre)=LOWER(?) "

            "AND r.author_id<>? "

            "ORDER BY RANDOM() LIMIT ?",

            (user["favorite_genre"], user_id, limit),

        ).fetchall()

        for r in rows:

            items.append(r); seen_ids.add(r["id"])

    if len(items) < limit:

        rows = conn.execute(

            "SELECT r.*, u.username AS author, u.avatar_emoji AS author_emoji FROM reviews r "

            "JOIN users u ON u.id=r.author_id "

            "WHERE r.is_hidden=0 AND r.is_draft=0 AND r.author_id<>? "

            f"AND r.id NOT IN ({','.join(['?']*len(seen_ids)) or '0'}) "

            "ORDER BY RANDOM() LIMIT ?",

            (user_id, *seen_ids, limit - len(items)),

        ).fetchall()

        items += list(rows)

    conn.close()

    return items





def force_drop_db():

                                                

    if os.path.exists(DB_PATH):

        os.remove(DB_PATH)

    init_db()

