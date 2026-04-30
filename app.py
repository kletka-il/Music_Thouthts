import _bootstrap

_bootstrap.ensure()



import os

import json

import random

from datetime import datetime, timedelta

from functools import wraps



from flask import (

    Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify,

    Response,

)

from werkzeug.security import check_password_hash, generate_password_hash



from database import (

    init_db, get_db, get_setting, set_setting,

    increment_visits, get_visits, log_mod_action, filter_banned_words,

    push_notification, recalc_achievements_for, ACHIEVEMENT_CATALOG,

    parse_tags, set_review_tags, get_review_tags, detect_embed,

    update_streak, get_song_of_day, random_lyric_quote, get_recommendations_for,

    NOTIF_KIND_RU, ROLE_RU, MOOD_OPTIONS, MOOD_LABELS,

)



app = Flask(__name__)

app.secret_key = os.environ.get("MT_SECRET", "music-thoughts-very-secret-2026")









def current_user():

    uid = session.get("user_id")

    if not uid:

        return None

    conn = get_db()

    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    conn.close()

    return row





def login_required(f):

    @wraps(f)

    def w(*a, **kw):

        if not current_user():

            flash("Войдите, чтобы продолжить", "error")

            return redirect(url_for("login"))

        return f(*a, **kw)

    return w





def role_required(*roles):

    def deco(f):

        @wraps(f)

        def w(*a, **kw):

            u = current_user()

            if not u:

                flash("Войдите, чтобы продолжить", "error")

                return redirect(url_for("login"))

            if u["role"] not in roles:

                flash("Доступ запрещён", "error")

                return redirect(url_for("index"))

            return f(*a, **kw)

        return w

    return deco





def get_unread_notifications_count(user_id):

    if not user_id:

        return 0

    conn = get_db()

    row = conn.execute(

        "SELECT COUNT(*) AS c FROM notifications WHERE user_id=? AND is_read=0",

        (user_id,),

    ).fetchone()

    conn.close()

    return row["c"] if row else 0





def get_unread_dm_count(user_id):

    if not user_id:

        return 0

    conn = get_db()

    row = conn.execute(

        "SELECT COUNT(*) AS c FROM dm_messages WHERE to_id=? AND is_read=0",

        (user_id,),

    ).fetchone()

    conn.close()

    return row["c"] if row else 0





def is_following(follower_id, followee_id):

    if not follower_id or not followee_id or follower_id == followee_id:

        return False

    conn = get_db()

    row = conn.execute(

        "SELECT 1 FROM follows WHERE follower_id=? AND followee_id=?",

        (follower_id, followee_id),

    ).fetchone()

    conn.close()

    return bool(row)





def is_bookmarked(user_id, review_id):

    if not user_id:

        return False

    conn = get_db()

    row = conn.execute(

        "SELECT 1 FROM bookmarks WHERE user_id=? AND review_id=?",

        (user_id, review_id),

    ).fetchone()

    conn.close()

    return bool(row)





@app.context_processor

def inject_globals():

    u = current_user()

    return {

        "current_user": u,

        "site_banner": get_setting("site_banner", ""),

        "site_tagline": get_setting("site_tagline", ""),

        "site_quote": get_setting("site_quote", ""),

        "visits": get_visits(),

        "now_year": datetime.utcnow().year,

        "unread_count": get_unread_notifications_count(u["id"]) if u else 0,

        "unread_dm": get_unread_dm_count(u["id"]) if u else 0,

        "ACHIEVEMENT_CATALOG": ACHIEVEMENT_CATALOG,

        "ROLE_RU": ROLE_RU,

        "MOOD_OPTIONS": MOOD_OPTIONS,

        "MOOD_LABELS": MOOD_LABELS,

    }





@app.template_filter("embed_url")

def embed_url_filter(url):

    return detect_embed(url) or ""





@app.template_filter("nicedate")

def nicedate(s):

    if not s:

        return ""

    try:

        dt = datetime.fromisoformat(s)

        return dt.strftime("%d.%m.%Y %H:%M")

    except Exception:

        return s[:16].replace("T", " ")





@app.template_filter("nicedateonly")

def nicedateonly(s):

    if not s:

        return ""

    try:

        dt = datetime.fromisoformat(s)

        return dt.strftime("%d.%m.%Y")

    except Exception:

        return s[:10]





@app.template_filter("ago")

def ago(s):

    if not s:

        return ""

    try:

        dt = datetime.fromisoformat(s)

    except Exception:

        return s

    diff = datetime.utcnow() - dt

    sec = int(diff.total_seconds())

    if sec < 0:

        sec = 0

    if sec < 60:

        return "только что"

    if sec < 3600:

        return f"{sec // 60} мин назад"

    if sec < 86400:

        return f"{sec // 3600} ч назад"

    if sec < 30 * 86400:

        return f"{sec // 86400} д назад"

    return dt.strftime("%d.%m.%Y")





@app.template_filter("until")

def until(s):

    if not s:

        return ""

    try:

        dt = datetime.fromisoformat(s)

    except Exception:

        return s

    diff = dt - datetime.utcnow()

    sec = int(diff.total_seconds())

    if sec <= 0:

        return "уже идёт"

    if sec < 3600:

        return f"через {sec // 60} мин"

    if sec < 86400:

        return f"через {sec // 3600} ч"

    return f"через {sec // 86400} дн"





@app.template_filter("kind_ru")

def kind_ru_filter(k):

    return NOTIF_KIND_RU.get(k or "", "Уведомление")





@app.template_filter("role_ru")

def role_ru_filter(r):

    return ROLE_RU.get(r or "", "—")





@app.template_filter("mood_ru")

def mood_ru_filter(code):

    return MOOD_LABELS.get(code or "", "")





@app.before_request

def before():

    if request.endpoint and request.endpoint != "static":

        increment_visits()

    u = current_user()

    if u:

        update_streak(u["id"])









@app.route("/")

def index():

    conn = get_db()

    featured = conn.execute(

        "SELECT r.*, u.username AS author, u.avatar_emoji AS author_emoji "

        "FROM reviews r JOIN users u ON u.id=r.author_id "

        "WHERE r.is_hidden=0 AND r.is_draft=0 AND r.is_featured=1 "

        "ORDER BY r.created_at DESC LIMIT 3"

    ).fetchall()

    latest = conn.execute(

        "SELECT r.*, u.username AS author, u.avatar_emoji AS author_emoji "

        "FROM reviews r JOIN users u ON u.id=r.author_id "

        "WHERE r.is_hidden=0 AND r.is_draft=0 ORDER BY r.created_at DESC LIMIT 8"

    ).fetchall()

    top = conn.execute(

        "SELECT r.*, u.username AS author, "

        "(SELECT COALESCE(SUM(value),0) FROM ratings WHERE review_id=r.id) AS net_rating "

        "FROM reviews r JOIN users u ON u.id=r.author_id "

        "WHERE r.is_hidden=0 AND r.is_draft=0 ORDER BY net_rating DESC, r.score DESC LIMIT 5"

    ).fetchall()

    popular_tags = conn.execute(

        "SELECT t.name, COUNT(*) AS c FROM tags t JOIN review_tags rt ON rt.tag_id=t.id "

        "GROUP BY t.id ORDER BY c DESC LIMIT 12"

    ).fetchall()

    upcoming = conn.execute(

        "SELECT * FROM events WHERE is_hidden=0 AND starts_at>=? "

        "ORDER BY starts_at ASC LIMIT 3",

        (datetime.utcnow().isoformat(),),

    ).fetchall()

    active_challenge = conn.execute(

        "SELECT * FROM challenges WHERE is_hidden=0 AND ends_at>=? "

        "ORDER BY ends_at ASC LIMIT 1",

        (datetime.utcnow().isoformat(),),

    ).fetchone()

    active_poll = conn.execute(

        "SELECT * FROM polls WHERE is_closed=0 AND is_hidden=0 "

        "ORDER BY created_at DESC LIMIT 1"

    ).fetchone()

    conn.close()

    sotd = get_song_of_day()

    quote = random_lyric_quote()

    return render_template(

        "index.html",

        featured=featured, latest=latest, top=top, popular_tags=popular_tags,

        upcoming=upcoming, active_challenge=active_challenge, active_poll=active_poll,

        sotd=sotd, quote=quote,

    )









@app.route("/register", methods=["GET", "POST"])

def register():

    if get_setting("registration_open", "1") != "1":

        flash("Регистрация временно закрыта", "error")

        return redirect(url_for("login"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()

        email = request.form.get("email", "").strip()

        password = request.form.get("password", "")

        role = request.form.get("role", "viewer")

        if role not in ("viewer", "reviewer"):

            role = "viewer"

        if not username or not email or len(password) < 4:

            flash("Заполните все поля (пароль не короче 4 символов)", "error")

            return render_template("register.html")

        conn = get_db()

        try:

            conn.execute(

                "INSERT INTO users(username,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",

                (username, email, generate_password_hash(password), role, datetime.utcnow().isoformat()),

            )

            conn.commit()

        except Exception as e:

            conn.close()

            flash(f"Ошибка регистрации: {e}", "error")

            return render_template("register.html")

        conn.close()

        flash("Аккаунт создан! Войдите.", "ok")

        return redirect(url_for("login"))

    return render_template("register.html")





@app.route("/login", methods=["GET", "POST"])

def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()

        password = request.form.get("password", "")

        conn = get_db()

        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

        if not row or not check_password_hash(row["password_hash"], password):

            conn.close()

            flash("Неверный логин или пароль", "error")

            return render_template("login.html")

        if row["is_banned"]:

            conn.close()

            flash(f"Аккаунт заблокирован. Причина: {row['ban_reason'] or 'не указана'}", "error")

            return render_template("login.html")

        conn.execute("UPDATE users SET last_login=? WHERE id=?",

                     (datetime.utcnow().isoformat(), row["id"]))

        conn.commit()

        conn.close()

        session["user_id"] = row["id"]

        update_streak(row["id"])

        recalc_achievements_for(row["id"])

        flash(f"Привет, {row['username']}!", "ok")

        return redirect(url_for("index"))

    return render_template("login.html")





@app.route("/logout")

def logout():

    session.clear()

    flash("Вы вышли", "ok")

    return redirect(url_for("index"))





@app.route("/password/change", methods=["GET", "POST"])

@login_required

def password_change():

    u = current_user()

    if request.method == "POST":

        old = request.form.get("old", "")

        new = request.form.get("new", "")

        if not check_password_hash(u["password_hash"], old):

            flash("Текущий пароль неверен", "error")

            return render_template("password_change.html")

        if len(new) < 4:

            flash("Новый пароль должен быть не короче 4 символов", "error")

            return render_template("password_change.html")

        conn = get_db()

        conn.execute("UPDATE users SET password_hash=? WHERE id=?",

                     (generate_password_hash(new), u["id"]))

        conn.commit()

        conn.close()

        flash("Пароль обновлён", "ok")

        return redirect(url_for("profile", username=u["username"]))

    return render_template("password_change.html")









@app.route("/reviews")

def reviews_list():

    q = request.args.get("q", "").strip()

    genre = request.args.get("genre", "").strip()

    tag = request.args.get("tag", "").strip().lower()

    mood = request.args.get("mood", "").strip()

    sort = request.args.get("sort", "new")

    year_from = request.args.get("year_from", "").strip()

    year_to = request.args.get("year_to", "").strip()

    score_min = request.args.get("score_min", "").strip()

    conn = get_db()

    sql = (

        "SELECT r.*, u.username AS author, u.avatar_emoji AS author_emoji, "

        "(SELECT COALESCE(SUM(value),0) FROM ratings WHERE review_id=r.id) AS net_rating, "

        "(SELECT COUNT(*) FROM comments WHERE review_id=r.id AND is_hidden=0) AS cn "

        "FROM reviews r JOIN users u ON u.id=r.author_id "

        "WHERE r.is_hidden=0 AND r.is_draft=0"

    )

    params = []

    if q:

        sql += " AND (r.artist LIKE ? OR r.title LIKE ? OR r.body LIKE ?)"

        like = f"%{q}%"

        params += [like, like, like]

    if genre:

        sql += " AND r.genre = ?"

        params.append(genre)

    if mood:

        sql += " AND r.mood = ?"

        params.append(mood)

    if tag:

        sql += (" AND r.id IN (SELECT review_id FROM review_tags rt "

                "JOIN tags t ON t.id=rt.tag_id WHERE t.name=?)")

        params.append(tag)

    if year_from.isdigit():

        sql += " AND r.year >= ?"

        params.append(int(year_from))

    if year_to.isdigit():

        sql += " AND r.year <= ?"

        params.append(int(year_to))

    if score_min.isdigit():

        sql += " AND r.score >= ?"

        params.append(int(score_min))

    if sort == "top":

        sql += " ORDER BY net_rating DESC, r.score DESC"

    elif sort == "score":

        sql += " ORDER BY r.score DESC"

    elif sort == "views":

        sql += " ORDER BY r.views DESC"

    elif sort == "old":

        sql += " ORDER BY r.created_at ASC"

    else:

        sql += " ORDER BY r.created_at DESC"

    rows = conn.execute(sql, params).fetchall()

    genres = conn.execute(

        "SELECT DISTINCT genre FROM reviews WHERE genre<>'' AND is_draft=0 ORDER BY genre"

    ).fetchall()

    conn.close()

    return render_template(

        "reviews_list.html", reviews=rows, q=q, genre=genre, tag=tag, sort=sort,

        mood=mood, genres=genres, year_from=year_from, year_to=year_to, score_min=score_min,

    )





@app.route("/discover")

def discover():

    conn = get_db()

    row = conn.execute(

        "SELECT id FROM reviews WHERE is_hidden=0 AND is_draft=0 ORDER BY RANDOM() LIMIT 1"

    ).fetchone()

    conn.close()

    if not row:

        flash("Нет рецензий", "error")

        return redirect(url_for("reviews_list"))

    return redirect(url_for("review_detail", rid=row["id"]))





@app.route("/tag/<name>")

def tag_browse(name):

    return redirect(url_for("reviews_list", tag=name.lower()))





@app.route("/review/<int:rid>")

def review_detail(rid):

    conn = get_db()

    conn.execute("UPDATE reviews SET views = views + 1 WHERE id=?", (rid,))

    conn.commit()

    r = conn.execute(

        "SELECT r.*, u.username AS author, u.avatar_emoji AS author_emoji "

        "FROM reviews r JOIN users u ON u.id=r.author_id WHERE r.id=?",

        (rid,),

    ).fetchone()

    if not r:

        conn.close()

        abort(404)

    u = current_user()

    is_owner = u and u["id"] == r["author_id"]

    if (r["is_hidden"] or r["is_draft"]) and not (u and (u["role"] == "moderator" or is_owner)):

        conn.close()

        abort(404)

    comments = conn.execute(

        "SELECT c.*, u.username AS author, u.avatar_emoji AS emoji, u.role AS author_role, "

        "(SELECT COALESCE(SUM(value),0) FROM comment_ratings WHERE comment_id=c.id) AS net "

        "FROM comments c JOIN users u ON u.id=c.author_id "

        "WHERE c.review_id=? ORDER BY c.created_at ASC",

        (rid,),

    ).fetchall()

    net = conn.execute(

        "SELECT COALESCE(SUM(value),0) AS s, COUNT(*) AS n FROM ratings WHERE review_id=?",

        (rid,),

    ).fetchone()

    user_rating = None

    user_comment_votes = {}

    if u:

        ur = conn.execute(

            "SELECT value FROM ratings WHERE review_id=? AND user_id=?", (rid, u["id"])

        ).fetchone()

        if ur:

            user_rating = ur["value"]

        for cv in conn.execute(

            "SELECT comment_id, value FROM comment_ratings WHERE user_id=? AND comment_id IN "

            f"(SELECT id FROM comments WHERE review_id={int(rid)})",

            (u["id"],),

        ).fetchall():

            user_comment_votes[cv["comment_id"]] = cv["value"]

    tags = get_review_tags(rid)

    similar = conn.execute(

        "SELECT r.*, u.username AS author, u.avatar_emoji AS author_emoji "

        "FROM reviews r JOIN users u ON u.id=r.author_id "

        "WHERE r.is_hidden=0 AND r.is_draft=0 AND r.id<>? "

        "AND (r.genre=? OR r.author_id=?) "

        "ORDER BY r.created_at DESC LIMIT 4",

        (rid, r["genre"], r["author_id"]),

    ).fetchall()

    conn.close()

    bookmarked = is_bookmarked(u["id"], rid) if u else False

    embed = detect_embed(r["listen_url"])

    ts_conn = get_db()

    ts_row = ts_conn.execute(

        "SELECT ROUND(AVG(value),1) AS avg, COUNT(*) AS n FROM track_scores WHERE review_id=?",

        (rid,),

    ).fetchone()

    track_avg = ts_row["avg"]

    track_count = ts_row["n"] or 0

    user_track_score = None

    if u:

        ur = ts_conn.execute(

            "SELECT value FROM track_scores WHERE review_id=? AND user_id=?", (rid, u["id"])

        ).fetchone()

        if ur:

            user_track_score = ur["value"]

    ts_conn.close()

    return render_template(

        "review_detail.html", r=r, comments=comments,

        net_rating=net["s"], rating_count=net["n"], user_rating=user_rating,

        tags=tags, embed=embed, bookmarked=bookmarked, is_owner=is_owner,

        user_comment_votes=user_comment_votes, similar=similar,

        track_avg=track_avg, track_count=track_count, user_track_score=user_track_score,

    )





@app.route("/review/new", methods=["GET", "POST"])

@role_required("reviewer", "moderator")

def review_new():

    if request.method == "POST":

        return _save_review(None)

    return render_template("review_form.html", r=None, tags_str="")





@app.route("/review/<int:rid>/edit", methods=["GET", "POST"])

@login_required

def review_edit(rid):

    conn = get_db()

    r = conn.execute("SELECT * FROM reviews WHERE id=?", (rid,)).fetchone()

    conn.close()

    if not r:

        abort(404)

    u = current_user()

    if u["role"] != "moderator" and r["author_id"] != u["id"]:

        flash("Это не ваша рецензия", "error")

        return redirect(url_for("review_detail", rid=rid))

    if request.method == "POST":

        return _save_review(rid)

    tags_str = ", ".join(get_review_tags(rid))

    return render_template("review_form.html", r=r, tags_str=tags_str)





def _save_review(rid):

    u = current_user()

    artist = request.form.get("artist", "").strip()

    title = request.form.get("title", "").strip()

    genre = request.form.get("genre", "").strip()

    year = request.form.get("year", "").strip()

    cover = request.form.get("cover_url", "").strip()

    listen = request.form.get("listen_url", "").strip()

    body = request.form.get("body", "").strip()

    tags_str = request.form.get("tags", "")

    mood = request.form.get("mood", "").strip()

    if mood and mood not in MOOD_LABELS:

        mood = ""

    is_draft = 1 if request.form.get("is_draft") else 0

    try:

        score = max(1, min(10, int(request.form.get("score", "5"))))

    except ValueError:

        score = 5

    if not artist or not title or not body:

        flash("Заполните исполнителя, название и текст", "error")

        return render_template("review_form.html", r=None, tags_str=tags_str)

    body = filter_banned_words(body)

    try:

        year_int = int(year) if year else None

    except ValueError:

        year_int = None

    now = datetime.utcnow().isoformat()

    conn = get_db()

    if rid is None:

        cur = conn.execute(

            "INSERT INTO reviews(author_id,artist,title,genre,year,cover_url,listen_url,"

            "body,score,mood,is_draft,created_at,updated_at) "

            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",

            (u["id"], artist, title, genre, year_int, cover, listen, body, score, mood,

             is_draft, now, now),

        )

        rid = cur.lastrowid

        conn.commit()

        conn.close()

        set_review_tags(rid, parse_tags(tags_str))

        recalc_achievements_for(u["id"])

        if not is_draft:

            _notify_followers(u["id"], "new_review",

                              f"{u['username']} опубликовал(а) рецензию: {artist} — {title}",

                              link=f"/review/{rid}")

        flash("Готово!", "ok")

    else:

        r = conn.execute("SELECT * FROM reviews WHERE id=?", (rid,)).fetchone()

        was_draft = r["is_draft"]

        conn.execute(

            "UPDATE reviews SET artist=?,title=?,genre=?,year=?,cover_url=?,listen_url=?,"

            "body=?,score=?,mood=?,is_draft=?,updated_at=? WHERE id=?",

            (artist, title, genre, year_int, cover, listen, body, score, mood, is_draft,

             datetime.utcnow().isoformat(), rid),

        )

        conn.commit()

        conn.close()

        set_review_tags(rid, parse_tags(tags_str))

        if u["role"] == "moderator" and r["author_id"] != u["id"]:

            log_mod_action(u["id"], "edit_review", f"review #{rid}")

        if was_draft and not is_draft:

            _notify_followers(r["author_id"], "new_review",

                              f"Опубликована рецензия: {artist} — {title}", link=f"/review/{rid}")

        flash("Сохранено", "ok")

    return redirect(url_for("review_detail", rid=rid))





def _notify_followers(author_id, kind, body, link):

    conn = get_db()

    rows = conn.execute("SELECT follower_id FROM follows WHERE followee_id=?", (author_id,)).fetchall()

    conn.close()

    for r in rows:

        push_notification(r["follower_id"], kind, body, link)





@app.route("/review/<int:rid>/delete", methods=["POST"])

@login_required

def review_delete(rid):

    u = current_user()

    conn = get_db()

    r = conn.execute("SELECT * FROM reviews WHERE id=?", (rid,)).fetchone()

    if not r:

        conn.close()

        abort(404)

    if u["role"] != "moderator" and r["author_id"] != u["id"]:

        conn.close()

        flash("Нет прав на удаление", "error")

        return redirect(url_for("review_detail", rid=rid))

    conn.execute("DELETE FROM reviews WHERE id=?", (rid,))

    conn.commit()

    conn.close()

    if u["role"] == "moderator" and r["author_id"] != u["id"]:

        log_mod_action(u["id"], "delete_review", f"review #{rid}")

    flash("Рецензия удалена", "ok")

    return redirect(url_for("reviews_list"))









@app.route("/review/<int:rid>/rate", methods=["POST"])

@login_required

def review_rate(rid):

    u = current_user()

    try:

        v = int(request.form.get("value", "0"))

    except ValueError:

        v = 0

    if v not in (-1, 0, 1):

        v = 0

    conn = get_db()

    if v == 0:

        conn.execute("DELETE FROM ratings WHERE review_id=? AND user_id=?", (rid, u["id"]))

    else:

        conn.execute(

            "INSERT INTO ratings(review_id,user_id,value,created_at) VALUES (?,?,?,?) "

            "ON CONFLICT(review_id,user_id) DO UPDATE SET value=excluded.value",

            (rid, u["id"], v, datetime.utcnow().isoformat()),

        )

    r = conn.execute("SELECT author_id, artist, title FROM reviews WHERE id=?", (rid,)).fetchone()

    conn.commit()

    conn.close()

    if v == 1 and r and r["author_id"] != u["id"]:

        push_notification(r["author_id"], "rating",

                          f"{u['username']} отметил(а) рецензию «{r['artist']} — {r['title']}»",

                          link=f"/review/{rid}")

        recalc_achievements_for(r["author_id"])

    return redirect(url_for("review_detail", rid=rid))





@app.route("/review/<int:rid>/score", methods=["POST"])

@login_required

def track_score(rid):

    u = current_user()

    try:

        v = int(request.form.get("value", "0"))

    except ValueError:

        v = 0

    conn = get_db()

    r = conn.execute("SELECT id, author_id, artist, title FROM reviews WHERE id=?", (rid,)).fetchone()

    if not r:

        conn.close()

        abort(404)

    if v == 0:

        conn.execute("DELETE FROM track_scores WHERE review_id=? AND user_id=?", (rid, u["id"]))

    elif 1 <= v <= 10:

        conn.execute(

            "INSERT INTO track_scores(review_id,user_id,value,created_at) VALUES (?,?,?,?) "

            "ON CONFLICT(review_id,user_id) DO UPDATE SET value=excluded.value, created_at=excluded.created_at",

            (rid, u["id"], v, datetime.utcnow().isoformat()),

        )

    conn.commit()

    conn.close()

    if 1 <= v <= 10 and r["author_id"] != u["id"]:

        push_notification(r["author_id"], "rating",

                          f"{u['username']} поставил(а) {v}/10 треку «{r['artist']} — {r['title']}»",

                          link=f"/review/{rid}")

    return redirect(url_for("review_detail", rid=rid) + "#track-rating")





@app.route("/comment/<int:cid>/rate", methods=["POST"])

@login_required

def comment_rate(cid):

    u = current_user()

    try:

        v = int(request.form.get("value", "0"))

    except ValueError:

        v = 0

    if v not in (-1, 0, 1):

        v = 0

    conn = get_db()

    c = conn.execute("SELECT review_id FROM comments WHERE id=?", (cid,)).fetchone()

    if not c:

        conn.close()

        abort(404)

    if v == 0:

        conn.execute("DELETE FROM comment_ratings WHERE comment_id=? AND user_id=?", (cid, u["id"]))

    else:

        conn.execute(

            "INSERT INTO comment_ratings(comment_id,user_id,value,created_at) VALUES (?,?,?,?) "

            "ON CONFLICT(comment_id,user_id) DO UPDATE SET value=excluded.value",

            (cid, u["id"], v, datetime.utcnow().isoformat()),

        )

    conn.commit()

    conn.close()

    return redirect(url_for("review_detail", rid=c["review_id"]) + f"#c{cid}")









@app.route("/review/<int:rid>/comment", methods=["POST"])

@login_required

def comment_add(rid):

    u = current_user()

    body = filter_banned_words(request.form.get("body", "").strip())

    parent = request.form.get("parent_id")

    parent_id = int(parent) if parent and parent.isdigit() else None

    if not body:

        flash("Пустой комментарий", "error")

        return redirect(url_for("review_detail", rid=rid))

    conn = get_db()

    cur = conn.execute(

        "INSERT INTO comments(review_id,author_id,parent_id,body,created_at) VALUES (?,?,?,?,?)",

        (rid, u["id"], parent_id, body, datetime.utcnow().isoformat()),

    )

    cid = cur.lastrowid

    r = conn.execute("SELECT author_id FROM reviews WHERE id=?", (rid,)).fetchone()

    parent_author = None

    if parent_id:

        p = conn.execute("SELECT author_id FROM comments WHERE id=?", (parent_id,)).fetchone()

        parent_author = p["author_id"] if p else None

    conn.commit()

    conn.close()

    if r and r["author_id"] != u["id"]:

        push_notification(r["author_id"], "comment",

                          f"{u['username']} оставил(а) комментарий",

                          link=f"/review/{rid}#c{cid}")

    if parent_author and parent_author != u["id"]:

        push_notification(parent_author, "reply",

                          f"{u['username']} ответил(а) на ваш комментарий",

                          link=f"/review/{rid}#c{cid}")

    recalc_achievements_for(u["id"])

    return redirect(url_for("review_detail", rid=rid) + f"#c{cid}")





@app.route("/comment/<int:cid>/edit", methods=["POST"])

@login_required

def comment_edit(cid):

    u = current_user()

    body = filter_banned_words(request.form.get("body", "").strip())

    if not body:

        return redirect(request.referrer or url_for("index"))

    conn = get_db()

    c = conn.execute("SELECT * FROM comments WHERE id=?", (cid,)).fetchone()

    if not c:

        conn.close()

        abort(404)

    if u["role"] != "moderator" and c["author_id"] != u["id"]:

        conn.close()

        flash("Нет прав", "error")

        return redirect(url_for("review_detail", rid=c["review_id"]))

    conn.execute("UPDATE comments SET body=? WHERE id=?", (body, cid))

    conn.commit()

    conn.close()

    return redirect(url_for("review_detail", rid=c["review_id"]) + f"#c{cid}")





@app.route("/comment/<int:cid>/delete", methods=["POST"])

@login_required

def comment_delete(cid):

    u = current_user()

    conn = get_db()

    c = conn.execute("SELECT * FROM comments WHERE id=?", (cid,)).fetchone()

    if not c:

        conn.close()

        abort(404)

    if u["role"] != "moderator" and c["author_id"] != u["id"]:

        conn.close()

        flash("Нет прав", "error")

        return redirect(url_for("review_detail", rid=c["review_id"]))

    conn.execute("DELETE FROM comments WHERE id=?", (cid,))

    conn.commit()

    conn.close()

    if u["role"] == "moderator" and c["author_id"] != u["id"]:

        log_mod_action(u["id"], "delete_comment", f"comment #{cid}")

    return redirect(url_for("review_detail", rid=c["review_id"]))









@app.route("/bookmark/<int:rid>", methods=["POST"])

@login_required

def bookmark_toggle(rid):

    u = current_user()

    conn = get_db()

    exists = conn.execute(

        "SELECT 1 FROM bookmarks WHERE user_id=? AND review_id=?", (u["id"], rid)

    ).fetchone()

    if exists:

        conn.execute("DELETE FROM bookmarks WHERE user_id=? AND review_id=?", (u["id"], rid))

    else:

        conn.execute(

            "INSERT INTO bookmarks(user_id,review_id,created_at) VALUES (?,?,?)",

            (u["id"], rid, datetime.utcnow().isoformat()),

        )

    conn.commit()

    conn.close()

    return redirect(request.referrer or url_for("review_detail", rid=rid))





@app.route("/bookmarks")

@login_required

def my_bookmarks():

    u = current_user()

    conn = get_db()

    rows = conn.execute(

        "SELECT r.*, u.username AS author FROM bookmarks b "

        "JOIN reviews r ON r.id=b.review_id JOIN users u ON u.id=r.author_id "

        "WHERE b.user_id=? ORDER BY b.created_at DESC",

        (u["id"],),

    ).fetchall()

    conn.close()

    return render_template("bookmarks.html", reviews=rows)









@app.route("/follow/<username>", methods=["POST"])

@login_required

def follow(username):

    u = current_user()

    conn = get_db()

    target = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()

    if not target or target["id"] == u["id"]:

        conn.close()

        return redirect(url_for("profile", username=username))

    conn.execute(

        "INSERT OR IGNORE INTO follows(follower_id,followee_id,created_at) VALUES (?,?,?)",

        (u["id"], target["id"], datetime.utcnow().isoformat()),

    )

    conn.commit()

    conn.close()

    push_notification(target["id"], "follow", f"{u['username']} подписался(-ась)",

                      link=f"/u/{u['username']}")

    recalc_achievements_for(target["id"])

    return redirect(url_for("profile", username=username))





@app.route("/unfollow/<username>", methods=["POST"])

@login_required

def unfollow(username):

    u = current_user()

    conn = get_db()

    target = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()

    if target:

        conn.execute("DELETE FROM follows WHERE follower_id=? AND followee_id=?",

                     (u["id"], target["id"]))

        conn.commit()

    conn.close()

    return redirect(url_for("profile", username=username))





@app.route("/feed")

@login_required

def feed():

    u = current_user()

    conn = get_db()

    rows = conn.execute(

        "SELECT r.*, us.username AS author, us.avatar_emoji AS author_emoji "

        "FROM reviews r JOIN users us ON us.id=r.author_id "

        "WHERE r.is_hidden=0 AND r.is_draft=0 AND r.author_id IN ("

        "SELECT followee_id FROM follows WHERE follower_id=?) "

        "ORDER BY r.created_at DESC LIMIT 50",

        (u["id"],),

    ).fetchall()

    conn.close()

    return render_template("feed.html", reviews=rows)









@app.route("/notifications")

@login_required

def notifications():

    u = current_user()

    conn = get_db()

    rows = conn.execute(

        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 100",

        (u["id"],),

    ).fetchall()

    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0", (u["id"],))

    conn.commit()

    conn.close()

    return render_template("notifications.html", items=rows)









@app.route("/u/<username>")

def profile(username):

    if username == "_self":

        u = current_user()

        if not u:

            return redirect(url_for("login"))

        return redirect(url_for("profile", username=u["username"]))

    conn = get_db()

    user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

    if not user:

        conn.close()

        abort(404)

    reviews = conn.execute(

        "SELECT r.*, "

        "(SELECT COALESCE(SUM(value),0) FROM ratings WHERE review_id=r.id) AS net "

        "FROM reviews r WHERE author_id=? AND is_hidden=0 AND is_draft=0 "

        "ORDER BY created_at DESC",

        (user["id"],),

    ).fetchall()

    comments = conn.execute(

        "SELECT c.*, r.artist, r.title FROM comments c JOIN reviews r ON r.id=c.review_id "

        "WHERE c.author_id=? AND c.is_hidden=0 ORDER BY c.created_at DESC LIMIT 20",

        (user["id"],),

    ).fetchall()

    follower_count = conn.execute(

        "SELECT COUNT(*) AS c FROM follows WHERE followee_id=?", (user["id"],)

    ).fetchone()["c"]

    following_count = conn.execute(

        "SELECT COUNT(*) AS c FROM follows WHERE follower_id=?", (user["id"],)

    ).fetchone()["c"]

    achievements_list = conn.execute(

        "SELECT * FROM achievements WHERE user_id=? ORDER BY awarded_at DESC", (user["id"],)

    ).fetchall()

    playlists = conn.execute(

        "SELECT p.*, (SELECT COUNT(*) FROM playlist_items WHERE playlist_id=p.id) AS n "

        "FROM playlists p WHERE owner_id=? AND is_hidden=0 "

        "AND (is_public=1 OR ? = ?) ORDER BY created_at DESC",

        (user["id"], (current_user() or {"id": -1})["id"] if current_user() else -1, user["id"]),

    ).fetchall()

    diary = conn.execute(

        "SELECT * FROM listening_log WHERE user_id=? ORDER BY created_at DESC LIMIT 8",

        (user["id"],),

    ).fetchall()

    shoutouts_rows = conn.execute(

        "SELECT s.*, u.username AS author, u.avatar_emoji AS author_emoji "

        "FROM shoutouts s JOIN users u ON u.id=s.author_id "

        "WHERE s.profile_user_id=? AND s.is_hidden=0 ORDER BY s.created_at DESC LIMIT 10",

        (user["id"],),

    ).fetchall()

    conn.close()

    me = current_user()

    following = is_following(me["id"] if me else None, user["id"])

    return render_template(

        "profile.html", profile=user, reviews=reviews, comments=comments,

        follower_count=follower_count, following_count=following_count,

        following=following, achievements=achievements_list,

        playlists=playlists, diary=diary, shoutouts=shoutouts_rows,

    )





@app.route("/profile/edit", methods=["GET", "POST"])

@login_required

def profile_edit():

    u = current_user()

    if request.method == "POST":

        bio = request.form.get("bio", "")[:500]

        emoji = request.form.get("avatar_emoji", "🎵")[:8] or "🎵"

        theme = request.form.get("theme", "dark")

        if theme not in ("dark", "light"):

            theme = "dark"

        favorite_genre = request.form.get("favorite_genre", "")[:60].strip()

        spotify_link = request.form.get("spotify_link", "")[:200].strip()

        listening_now = request.form.get("listening_now", "")[:120].strip()

        conn = get_db()

        conn.execute(

            "UPDATE users SET bio=?, avatar_emoji=?, theme=?, favorite_genre=?, "

            "spotify_link=?, listening_now=? WHERE id=?",

            (bio, emoji, theme, favorite_genre, spotify_link, listening_now, u["id"]),

        )

        conn.commit()

        conn.close()

        flash("Профиль сохранён", "ok")

        return redirect(url_for("profile", username=u["username"]))

    return render_template("profile_edit.html", u=u)









@app.route("/shoutout/<username>", methods=["POST"])

@login_required

def shoutout_add(username):

    u = current_user()

    conn = get_db()

    target = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()

    if not target:

        conn.close()

        abort(404)

    body = filter_banned_words(request.form.get("body", "").strip())[:300]

    if body:

        conn.execute(

            "INSERT INTO shoutouts(profile_user_id,author_id,body,created_at) VALUES (?,?,?,?)",

            (target["id"], u["id"], body, datetime.utcnow().isoformat()),

        )

        conn.commit()

        if target["id"] != u["id"]:

            push_notification(target["id"], "shoutout",

                              f"{u['username']} оставил запись на вашей стене",

                              link=f"/u/{username}")

    conn.close()

    return redirect(url_for("profile", username=username))





@app.route("/shoutout/<int:sid>/delete", methods=["POST"])

@login_required

def shoutout_delete(sid):

    u = current_user()

    conn = get_db()

    s = conn.execute("SELECT * FROM shoutouts WHERE id=?", (sid,)).fetchone()

    if not s:

        conn.close()

        abort(404)

    target_user = conn.execute("SELECT username FROM users WHERE id=?", (s["profile_user_id"],)).fetchone()

    if u["role"] != "moderator" and u["id"] not in (s["author_id"], s["profile_user_id"]):

        conn.close()

        flash("Нет прав", "error")

        return redirect(url_for("index"))

    conn.execute("DELETE FROM shoutouts WHERE id=?", (sid,))

    conn.commit()

    conn.close()

    return redirect(url_for("profile", username=target_user["username"]))









@app.route("/leaderboard")

def leaderboard():

    conn = get_db()

    top_authors = conn.execute(

        "SELECT u.username, u.avatar_emoji, COUNT(r.id) AS n, "

        "COALESCE(SUM((SELECT COALESCE(SUM(value),0) FROM ratings WHERE review_id=r.id)),0) AS karma "

        "FROM users u LEFT JOIN reviews r ON r.author_id=u.id AND r.is_draft=0 "

        "GROUP BY u.id ORDER BY karma DESC, n DESC LIMIT 20"

    ).fetchall()

    top_commenters = conn.execute(

        "SELECT u.username, u.avatar_emoji, COUNT(c.id) AS n FROM users u "

        "LEFT JOIN comments c ON c.author_id=u.id GROUP BY u.id ORDER BY n DESC LIMIT 10"

    ).fetchall()

    most_followed = conn.execute(

        "SELECT u.username, u.avatar_emoji, COUNT(f.follower_id) AS n FROM users u "

        "LEFT JOIN follows f ON f.followee_id=u.id GROUP BY u.id "

        "HAVING n > 0 ORDER BY n DESC LIMIT 10"

    ).fetchall()

    streak_kings = conn.execute(

        "SELECT username, avatar_emoji, streak_days FROM users "

        "WHERE streak_days>0 ORDER BY streak_days DESC LIMIT 10"

    ).fetchall()

    conn.close()

    return render_template("leaderboard.html",

                           top_authors=top_authors,

                           top_commenters=top_commenters,

                           most_followed=most_followed,

                           streak_kings=streak_kings)









@app.route("/search")

def search():

    q = request.args.get("q", "").strip()

    return redirect(url_for("reviews_list", q=q))









@app.route("/report", methods=["POST"])

@login_required

def report():

    u = current_user()

    target_type = request.form.get("target_type", "")

    target_id = request.form.get("target_id", "0")

    reason = request.form.get("reason", "").strip()

    if target_type not in ("review", "comment", "user") or not reason:

        flash("Некорректная жалоба", "error")

        return redirect(request.referrer or url_for("index"))

    try:

        tid = int(target_id)

    except ValueError:

        tid = 0

    conn = get_db()

    conn.execute(

        "INSERT INTO reports(reporter_id,target_type,target_id,reason,created_at) VALUES (?,?,?,?,?)",

        (u["id"], target_type, tid, reason, datetime.utcnow().isoformat()),

    )

    conn.commit()

    conn.close()

    flash("Жалоба отправлена модераторам", "ok")

    return redirect(request.referrer or url_for("index"))









@app.route("/guestbook", methods=["GET", "POST"])

def guestbook():

    if request.method == "POST":

        if get_setting("guestbook_open", "1") != "1":

            flash("Гостевая закрыта", "error")

            return redirect(url_for("guestbook"))

        u = current_user()

        author = u["username"] if u else (request.form.get("author_name", "").strip() or "Аноним")

        body = filter_banned_words(request.form.get("body", "").strip())[:500]

        if body:

            conn = get_db()

            conn.execute(

                "INSERT INTO guestbook(author_name,body,created_at) VALUES (?,?,?)",

                (author, body, datetime.utcnow().isoformat()),

            )

            conn.commit()

            conn.close()

            flash("Запись добавлена", "ok")

        return redirect(url_for("guestbook"))

    conn = get_db()

    entries = conn.execute(

        "SELECT * FROM guestbook WHERE is_hidden=0 ORDER BY created_at DESC LIMIT 100"

    ).fetchall()

    conn.close()

    return render_template("guestbook.html", entries=entries)









@app.route("/playlists")

def playlists_list():

    conn = get_db()

    rows = conn.execute(

        "SELECT p.*, u.username AS owner, u.avatar_emoji AS owner_emoji, "

        "(SELECT COUNT(*) FROM playlist_items WHERE playlist_id=p.id) AS n "

        "FROM playlists p JOIN users u ON u.id=p.owner_id "

        "WHERE p.is_hidden=0 AND p.is_public=1 "

        "ORDER BY p.created_at DESC"

    ).fetchall()

    conn.close()

    return render_template("playlists_list.html", playlists=rows)





@app.route("/playlist/new", methods=["GET", "POST"])

@login_required

def playlist_new():

    u = current_user()

    if request.method == "POST":

        title = request.form.get("title", "").strip()[:80]

        description = request.form.get("description", "").strip()[:500]

        emoji = (request.form.get("cover_emoji", "🎶") or "🎶")[:6]

        is_public = 1 if request.form.get("is_public") else 0

        if not title:

            flash("Дайте подборке название", "error")

            return redirect(url_for("playlist_new"))

        conn = get_db()

        cur = conn.execute(

            "INSERT INTO playlists(owner_id,title,description,cover_emoji,is_public,created_at) "

            "VALUES (?,?,?,?,?,?)",

            (u["id"], title, description, emoji, is_public, datetime.utcnow().isoformat()),

        )

        pid = cur.lastrowid

        conn.commit()

        conn.close()

        recalc_achievements_for(u["id"])

        return redirect(url_for("playlist_detail", pid=pid))

    return render_template("playlist_form.html", p=None)





@app.route("/playlist/<int:pid>", methods=["GET", "POST"])

def playlist_detail(pid):

    conn = get_db()

    p = conn.execute(

        "SELECT p.*, u.username AS owner, u.avatar_emoji AS owner_emoji "

        "FROM playlists p JOIN users u ON u.id=p.owner_id WHERE p.id=?", (pid,),

    ).fetchone()

    if not p:

        conn.close()

        abort(404)

    if (p["is_hidden"] or not p["is_public"]):

        u = current_user()

        if not u or (u["id"] != p["owner_id"] and u["role"] != "moderator"):

            conn.close()

            abort(404)

    items = conn.execute(

        "SELECT pi.*, r.artist, r.title, r.score, r.cover_url, r.genre, r.listen_url, "

        "u.username AS r_author "

        "FROM playlist_items pi JOIN reviews r ON r.id=pi.review_id "

        "JOIN users u ON u.id=r.author_id "

        "WHERE pi.playlist_id=? ORDER BY pi.position ASC, r.id ASC",

        (pid,),

    ).fetchall()

    conn.close()

    return render_template("playlist_detail.html", p=p, items=items)





@app.route("/playlist/<int:pid>/edit", methods=["GET", "POST"])

@login_required

def playlist_edit(pid):

    u = current_user()

    conn = get_db()

    p = conn.execute("SELECT * FROM playlists WHERE id=?", (pid,)).fetchone()

    if not p:

        conn.close()

        abort(404)

    if u["role"] != "moderator" and p["owner_id"] != u["id"]:

        conn.close()

        flash("Нет прав", "error")

        return redirect(url_for("playlist_detail", pid=pid))

    if request.method == "POST":

        title = request.form.get("title", "").strip()[:80]

        description = request.form.get("description", "").strip()[:500]

        emoji = (request.form.get("cover_emoji", "🎶") or "🎶")[:6]

        is_public = 1 if request.form.get("is_public") else 0

        conn.execute(

            "UPDATE playlists SET title=?,description=?,cover_emoji=?,is_public=? WHERE id=?",

            (title, description, emoji, is_public, pid),

        )

        conn.commit()

        conn.close()

        flash("Сохранено", "ok")

        return redirect(url_for("playlist_detail", pid=pid))

    conn.close()

    return render_template("playlist_form.html", p=p)





@app.route("/playlist/<int:pid>/delete", methods=["POST"])

@login_required

def playlist_delete(pid):

    u = current_user()

    conn = get_db()

    p = conn.execute("SELECT * FROM playlists WHERE id=?", (pid,)).fetchone()

    if not p:

        conn.close()

        abort(404)

    if u["role"] != "moderator" and p["owner_id"] != u["id"]:

        conn.close()

        flash("Нет прав", "error")

        return redirect(url_for("playlist_detail", pid=pid))

    conn.execute("DELETE FROM playlists WHERE id=?", (pid,))

    conn.commit()

    conn.close()

    if u["role"] == "moderator" and p["owner_id"] != u["id"]:

        log_mod_action(u["id"], "delete_playlist", f"playlist #{pid}")

    flash("Подборка удалена", "ok")

    return redirect(url_for("playlists_list"))





@app.route("/playlist/<int:pid>/add/<int:rid>", methods=["POST"])

@login_required

def playlist_add_review(pid, rid):

    u = current_user()

    conn = get_db()

    p = conn.execute("SELECT * FROM playlists WHERE id=?", (pid,)).fetchone()

    if not p or (u["role"] != "moderator" and p["owner_id"] != u["id"]):

        conn.close()

        flash("Нет прав", "error")

        return redirect(request.referrer or url_for("index"))

    pos = conn.execute(

        "SELECT COALESCE(MAX(position),0)+1 AS p FROM playlist_items WHERE playlist_id=?", (pid,)

    ).fetchone()["p"]

    conn.execute(

        "INSERT OR IGNORE INTO playlist_items(playlist_id,review_id,position) VALUES (?,?,?)",

        (pid, rid, pos),

    )

    conn.commit()

    conn.close()

    flash("Добавлено в подборку", "ok")

    return redirect(request.referrer or url_for("playlist_detail", pid=pid))





@app.route("/playlist/<int:pid>/remove/<int:rid>", methods=["POST"])

@login_required

def playlist_remove_review(pid, rid):

    u = current_user()

    conn = get_db()

    p = conn.execute("SELECT * FROM playlists WHERE id=?", (pid,)).fetchone()

    if not p or (u["role"] != "moderator" and p["owner_id"] != u["id"]):

        conn.close()

        flash("Нет прав", "error")

        return redirect(url_for("playlist_detail", pid=pid))

    conn.execute("DELETE FROM playlist_items WHERE playlist_id=? AND review_id=?", (pid, rid))

    conn.commit()

    conn.close()

    return redirect(url_for("playlist_detail", pid=pid))









@app.route("/diary", methods=["GET", "POST"])

@login_required

def diary():

    u = current_user()

    if request.method == "POST":

        artist = request.form.get("artist", "").strip()[:100]

        title = request.form.get("title", "").strip()[:120]

        note = filter_banned_words(request.form.get("note", "").strip())[:500]

        mood = request.form.get("mood", "").strip()

        if mood not in MOOD_LABELS:

            mood = ""

        try:

            rating = max(0, min(10, int(request.form.get("rating", "0"))))

        except ValueError:

            rating = 0

        if artist:

            conn = get_db()

            conn.execute(

                "INSERT INTO listening_log(user_id,artist,title,note,mood,rating,created_at) "

                "VALUES (?,?,?,?,?,?,?)",

                (u["id"], artist, title, note, mood, rating, datetime.utcnow().isoformat()),

            )

            conn.commit()

            conn.close()

            recalc_achievements_for(u["id"])

            flash("Запись в дневник добавлена", "ok")

        return redirect(url_for("diary"))

    conn = get_db()

    rows = conn.execute(

        "SELECT * FROM listening_log WHERE user_id=? ORDER BY created_at DESC LIMIT 100",

        (u["id"],),

    ).fetchall()

    conn.close()

    return render_template("diary.html", entries=rows)





@app.route("/diary/<int:lid>/delete", methods=["POST"])

@login_required

def diary_delete(lid):

    u = current_user()

    conn = get_db()

    e = conn.execute("SELECT user_id FROM listening_log WHERE id=?", (lid,)).fetchone()

    if not e:

        conn.close()

        abort(404)

    if e["user_id"] != u["id"] and u["role"] != "moderator":

        conn.close()

        flash("Нет прав", "error")

        return redirect(url_for("diary"))

    conn.execute("DELETE FROM listening_log WHERE id=?", (lid,))

    conn.commit()

    conn.close()

    return redirect(url_for("diary"))









@app.route("/events")

def events_list():

    conn = get_db()

    upcoming = conn.execute(

        "SELECT e.*, "

        "(SELECT COUNT(*) FROM event_attendees WHERE event_id=e.id) AS att "

        "FROM events e WHERE is_hidden=0 AND starts_at>=? "

        "ORDER BY starts_at ASC",

        (datetime.utcnow().isoformat(),),

    ).fetchall()

    past = conn.execute(

        "SELECT e.*, "

        "(SELECT COUNT(*) FROM event_attendees WHERE event_id=e.id) AS att "

        "FROM events e WHERE is_hidden=0 AND starts_at<? "

        "ORDER BY starts_at DESC LIMIT 10",

        (datetime.utcnow().isoformat(),),

    ).fetchall()

    my_events = []

    u = current_user()

    if u:

        my_events = [r["event_id"] for r in get_db().execute(

            "SELECT event_id FROM event_attendees WHERE user_id=?", (u["id"],),

        ).fetchall()]

    conn.close()

    return render_template("events_list.html", upcoming=upcoming, past=past, my_events=my_events)





@app.route("/event/<int:eid>")

def event_detail(eid):

    conn = get_db()

    e = conn.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()

    if not e or e["is_hidden"]:

        conn.close()

        abort(404)

    attendees = conn.execute(

        "SELECT u.username, u.avatar_emoji FROM event_attendees a "

        "JOIN users u ON u.id=a.user_id WHERE a.event_id=? ORDER BY u.username",

        (eid,),

    ).fetchall()

    me = current_user()

    going = False

    if me:

        going = bool(conn.execute(

            "SELECT 1 FROM event_attendees WHERE event_id=? AND user_id=?", (eid, me["id"]),

        ).fetchone())

    conn.close()

    return render_template("event_detail.html", e=e, attendees=attendees, going=going)





@app.route("/event/<int:eid>/attend", methods=["POST"])

@login_required

def event_attend(eid):

    u = current_user()

    conn = get_db()

    conn.execute(

        "INSERT OR IGNORE INTO event_attendees(event_id,user_id) VALUES (?,?)",

        (eid, u["id"]),

    )

    conn.commit()

    conn.close()

    recalc_achievements_for(u["id"])

    flash("Записал вас на событие", "ok")

    return redirect(url_for("event_detail", eid=eid))





@app.route("/event/<int:eid>/leave", methods=["POST"])

@login_required

def event_leave(eid):

    u = current_user()

    conn = get_db()

    conn.execute("DELETE FROM event_attendees WHERE event_id=? AND user_id=?", (eid, u["id"]))

    conn.commit()

    conn.close()

    return redirect(url_for("event_detail", eid=eid))









@app.route("/polls")

def polls_list():

    conn = get_db()

    rows = conn.execute(

        "SELECT p.*, "

        "(SELECT COUNT(*) FROM poll_votes WHERE poll_id=p.id) AS vc "

        "FROM polls p WHERE is_hidden=0 ORDER BY is_closed ASC, created_at DESC"

    ).fetchall()

    conn.close()

    return render_template("polls_list.html", polls=rows)





@app.route("/poll/<int:pid>", methods=["GET", "POST"])

def poll_detail(pid):

    conn = get_db()

    p = conn.execute("SELECT * FROM polls WHERE id=?", (pid,)).fetchone()

    if not p or p["is_hidden"]:

        conn.close()

        abort(404)

    options = conn.execute(

        "SELECT o.*, "

        "(SELECT COUNT(*) FROM poll_votes WHERE option_id=o.id) AS vc "

        "FROM poll_options o WHERE poll_id=? ORDER BY o.id",

        (pid,),

    ).fetchall()

    me = current_user()

    my_vote = None

    if me:

        v = conn.execute(

            "SELECT option_id FROM poll_votes WHERE poll_id=? AND user_id=?", (pid, me["id"]),

        ).fetchone()

        if v:

            my_vote = v["option_id"]

    if request.method == "POST" and me and not p["is_closed"]:

        try:

            opt = int(request.form.get("option_id", "0"))

        except ValueError:

            opt = 0

        if any(o["id"] == opt for o in options):

            conn.execute(

                "INSERT INTO poll_votes(poll_id,option_id,user_id,created_at) VALUES (?,?,?,?) "

                "ON CONFLICT(poll_id,user_id) DO UPDATE SET option_id=excluded.option_id, "

                "created_at=excluded.created_at",

                (pid, opt, me["id"], datetime.utcnow().isoformat()),

            )

            conn.commit()

        conn.close()

        return redirect(url_for("poll_detail", pid=pid))

    total_votes = sum(o["vc"] for o in options) or 1

    conn.close()

    return render_template("poll_detail.html", p=p, options=options,

                           my_vote=my_vote, total=total_votes)









@app.route("/challenges")

def challenges_list():

    conn = get_db()

    active = conn.execute(

        "SELECT c.*, "

        "(SELECT COUNT(*) FROM challenge_submissions WHERE challenge_id=c.id) AS sc "

        "FROM challenges c WHERE is_hidden=0 AND ends_at>=? "

        "ORDER BY ends_at ASC",

        (datetime.utcnow().isoformat(),),

    ).fetchall()

    past = conn.execute(

        "SELECT c.*, "

        "(SELECT COUNT(*) FROM challenge_submissions WHERE challenge_id=c.id) AS sc "

        "FROM challenges c WHERE is_hidden=0 AND ends_at<? "

        "ORDER BY ends_at DESC LIMIT 10",

        (datetime.utcnow().isoformat(),),

    ).fetchall()

    conn.close()

    return render_template("challenges_list.html", active=active, past=past)





@app.route("/challenge/<int:cid>", methods=["GET", "POST"])

def challenge_detail(cid):

    conn = get_db()

    c = conn.execute("SELECT * FROM challenges WHERE id=?", (cid,)).fetchone()

    if not c or c["is_hidden"]:

        conn.close()

        abort(404)

    me = current_user()

    if request.method == "POST":

        if not me:

            conn.close()

            return redirect(url_for("login"))

        text = filter_banned_words(request.form.get("text", "").strip())[:1000]

        rid = request.form.get("review_id", "").strip()

        rid_int = int(rid) if rid.isdigit() else None

        if not text and not rid_int:

            flash("Опишите свой выбор или прикрепите рецензию", "error")

        else:

            conn.execute(

                "INSERT INTO challenge_submissions(challenge_id,user_id,review_id,text,created_at) "

                "VALUES (?,?,?,?,?) "

                "ON CONFLICT(challenge_id,user_id) DO UPDATE SET review_id=excluded.review_id, "

                "text=excluded.text, created_at=excluded.created_at",

                (cid, me["id"], rid_int, text, datetime.utcnow().isoformat()),

            )

            conn.commit()

            recalc_achievements_for(me["id"])

            flash("Заявка принята!", "ok")

        conn.close()

        return redirect(url_for("challenge_detail", cid=cid))

    submissions = conn.execute(

        "SELECT s.*, u.username AS author, u.avatar_emoji AS emoji, "

        "r.artist, r.title FROM challenge_submissions s "

        "JOIN users u ON u.id=s.user_id "

        "LEFT JOIN reviews r ON r.id=s.review_id "

        "WHERE s.challenge_id=? ORDER BY s.created_at DESC",

        (cid,),

    ).fetchall()

    my_subm = None

    if me:

        my_subm = conn.execute(

            "SELECT * FROM challenge_submissions WHERE challenge_id=? AND user_id=?",

            (cid, me["id"]),

        ).fetchone()

    my_reviews = []

    if me:

        my_reviews = conn.execute(

            "SELECT id, artist, title FROM reviews WHERE author_id=? AND is_draft=0 "

            "ORDER BY created_at DESC LIMIT 30",

            (me["id"],),

        ).fetchall()

    conn.close()

    return render_template("challenge_detail.html",

                           c=c, submissions=submissions, my_subm=my_subm,

                           my_reviews=my_reviews)









@app.route("/messages")

@login_required

def dm_inbox():

    u = current_user()

    conn = get_db()

    rows = conn.execute(

        """
        SELECT u2.id AS other_id, u2.username AS other, u2.avatar_emoji AS emoji,
               (SELECT body FROM dm_messages
                WHERE (from_id=u2.id AND to_id=?) OR (from_id=? AND to_id=u2.id)
                ORDER BY created_at DESC LIMIT 1) AS last_body,
               (SELECT created_at FROM dm_messages
                WHERE (from_id=u2.id AND to_id=?) OR (from_id=? AND to_id=u2.id)
                ORDER BY created_at DESC LIMIT 1) AS last_at,
               (SELECT COUNT(*) FROM dm_messages
                WHERE from_id=u2.id AND to_id=? AND is_read=0) AS unread
        FROM users u2
        WHERE u2.id IN (SELECT from_id FROM dm_messages WHERE to_id=?
                        UNION SELECT to_id FROM dm_messages WHERE from_id=?)
        ORDER BY last_at DESC
        """,

        (u["id"], u["id"], u["id"], u["id"], u["id"], u["id"], u["id"]),

    ).fetchall()

    conn.close()

    return render_template("dm_inbox.html", chats=rows)





@app.route("/messages/<username>", methods=["GET", "POST"])

@login_required

def dm_chat(username):

    u = current_user()

    conn = get_db()

    other = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

    if not other:

        conn.close()

        abort(404)

    if other["id"] == u["id"]:

        conn.close()

        flash("Нельзя писать самому себе", "error")

        return redirect(url_for("dm_inbox"))

    if request.method == "POST":

        body = filter_banned_words(request.form.get("body", "").strip())[:1000]

        if body:

            conn.execute(

                "INSERT INTO dm_messages(from_id,to_id,body,created_at) VALUES (?,?,?,?)",

                (u["id"], other["id"], body, datetime.utcnow().isoformat()),

            )

            conn.commit()

            push_notification(other["id"], "dm",

                              f"{u['username']} написал(а) вам",

                              link=f"/messages/{u['username']}")

        conn.close()

        return redirect(url_for("dm_chat", username=username))

    msgs = conn.execute(

        "SELECT * FROM dm_messages WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?) "

        "ORDER BY created_at ASC LIMIT 200",

        (u["id"], other["id"], other["id"], u["id"]),

    ).fetchall()

    conn.execute(

        "UPDATE dm_messages SET is_read=1 WHERE from_id=? AND to_id=? AND is_read=0",

        (other["id"], u["id"]),

    )

    conn.commit()

    conn.close()

    return render_template("dm_chat.html", other=other, msgs=msgs)









@app.route("/quotes")

def quotes_list():

    conn = get_db()

    rows = conn.execute(

        "SELECT q.*, u.username AS submitter FROM lyrics_quotes q "

        "LEFT JOIN users u ON u.id=q.submitted_by "

        "WHERE q.is_hidden=0 ORDER BY q.created_at DESC LIMIT 100"

    ).fetchall()

    conn.close()

    return render_template("quotes_list.html", quotes=rows)





@app.route("/quote/new", methods=["POST"])

@login_required

def quote_add():

    u = current_user()

    text = filter_banned_words(request.form.get("text", "").strip())[:300]

    artist = request.form.get("artist", "").strip()[:100]

    song = request.form.get("song", "").strip()[:100]

    if not text:

        flash("Введите цитату", "error")

        return redirect(url_for("quotes_list"))

    conn = get_db()

    conn.execute(

        "INSERT INTO lyrics_quotes(text,artist,song,submitted_by,created_at) VALUES (?,?,?,?,?)",

        (text, artist, song, u["id"], datetime.utcnow().isoformat()),

    )

    conn.commit()

    conn.close()

    recalc_achievements_for(u["id"])

    flash("Спасибо за цитату!", "ok")

    return redirect(url_for("quotes_list"))









@app.route("/quiz", methods=["GET", "POST"])

def quiz():

    conn = get_db()

    if request.method == "POST":

        u = current_user()

        if not u:

            conn.close()

            return redirect(url_for("login"))

        qids = request.form.getlist("qid")

        score = 0

        details = []

        for qid in qids:

            if not qid.isdigit():

                continue

            q = conn.execute("SELECT * FROM quiz_questions WHERE id=?", (int(qid),)).fetchone()

            if not q:

                continue

            try:

                ans = int(request.form.get(f"a_{qid}", "-1"))

            except ValueError:

                ans = -1

            ok = ans == q["correct"]

            if ok:

                score += 1

            details.append({

                "q": q["question"],

                "options": q["options"].split("|"),

                "ans": ans, "correct": q["correct"], "ok": ok,

                "explanation": q["explanation"],

            })

        total = len(details)

        conn.execute(

            "INSERT INTO quiz_attempts(user_id,score,total,created_at) VALUES (?,?,?,?)",

            (u["id"], score, total, datetime.utcnow().isoformat()),

        )

        conn.commit()

        conn.close()

        recalc_achievements_for(u["id"])

        return render_template("quiz_result.html",

                               score=score, total=total, details=details)

    questions = conn.execute(

        "SELECT * FROM quiz_questions WHERE is_hidden=0 ORDER BY RANDOM() LIMIT 5"

    ).fetchall()

    conn.close()

    qs = []

    for q in questions:

        qs.append({"id": q["id"], "question": q["question"], "options": q["options"].split("|")})

    return render_template("quiz.html", questions=qs)









@app.route("/recommend")

def recommend():

    u = current_user()

    if not u:

        return redirect(url_for("login"))

    items = get_recommendations_for(u["id"], limit=6)

    return render_template("recommend.html", items=items)









@app.route("/now_playing", methods=["POST"])

@login_required

def set_now_playing():

    u = current_user()

    val = request.form.get("listening_now", "").strip()[:120]

    conn = get_db()

    conn.execute("UPDATE users SET listening_now=? WHERE id=?", (val, u["id"]))

    conn.commit()

    conn.close()

    return redirect(request.referrer or url_for("profile", username=u["username"]))









@app.route("/mod/resolve_listen", methods=["POST"])

@role_required("moderator")

def mod_resolve_listen():

    from database import resolve_listen_urls

    n = resolve_listen_urls()

    flash(f"Подобрано видео для {n} треков", "ok")

    return redirect(url_for("mod_console"))





@app.route("/mod")

@role_required("moderator")

def mod_console():

    conn = get_db()

    open_reports = conn.execute("SELECT COUNT(*) AS c FROM reports WHERE status='open'").fetchone()["c"]

    user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]

    review_count = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"]

    comment_count = conn.execute("SELECT COUNT(*) AS c FROM comments").fetchone()["c"]

    banned_count = conn.execute("SELECT COUNT(*) AS c FROM users WHERE is_banned=1").fetchone()["c"]

    drafts_count = conn.execute("SELECT COUNT(*) AS c FROM reviews WHERE is_draft=1").fetchone()["c"]

    playlists_count = conn.execute("SELECT COUNT(*) AS c FROM playlists").fetchone()["c"]

    events_count = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]

    polls_count = conn.execute("SELECT COUNT(*) AS c FROM polls").fetchone()["c"]

    challenges_count = conn.execute("SELECT COUNT(*) AS c FROM challenges").fetchone()["c"]

    quotes_count = conn.execute("SELECT COUNT(*) AS c FROM lyrics_quotes").fetchone()["c"]

    quiz_count = conn.execute("SELECT COUNT(*) AS c FROM quiz_questions").fetchone()["c"]

    recent_log = conn.execute(

        "SELECT l.*, u.username FROM mod_log l JOIN users u ON u.id=l.moderator_id "

        "ORDER BY l.created_at DESC LIMIT 10"

    ).fetchall()

    conn.close()

    return render_template(

        "mod/console.html",

        open_reports=open_reports, user_count=user_count, review_count=review_count,

        comment_count=comment_count, banned_count=banned_count, drafts_count=drafts_count,

        playlists_count=playlists_count, events_count=events_count, polls_count=polls_count,

        challenges_count=challenges_count, quotes_count=quotes_count, quiz_count=quiz_count,

        recent_log=recent_log, motd=get_setting("moderator_motd", ""),

    )





@app.route("/mod/users")

@role_required("moderator")

def mod_users():

    q = request.args.get("q", "").strip()

    conn = get_db()

    if q:

        users = conn.execute(

            "SELECT * FROM users WHERE username LIKE ? OR email LIKE ? ORDER BY created_at DESC",

            (f"%{q}%", f"%{q}%"),

        ).fetchall()

    else:

        users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()

    conn.close()

    return render_template("mod/users.html", users=users, q=q)





@app.route("/mod/users/<int:uid>/role", methods=["POST"])

@role_required("moderator")

def mod_set_role(uid):

    me = current_user()

    new_role = request.form.get("role", "viewer")

    if new_role not in ("viewer", "reviewer", "moderator"):

        flash("Некорректная роль", "error")

        return redirect(url_for("mod_users"))

    conn = get_db()

    conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, uid))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "change_role", f"user #{uid} -> {new_role}")

    push_notification(uid, "role", f"Ваша роль изменена на «{ROLE_RU.get(new_role, new_role)}»",

                      link="/u/_self")

    recalc_achievements_for(uid)

    flash("Роль изменена", "ok")

    return redirect(url_for("mod_users"))





@app.route("/mod/users/<int:uid>/ban", methods=["POST"])

@role_required("moderator")

def mod_ban(uid):

    me = current_user()

    if uid == me["id"]:

        flash("Нельзя забанить себя", "error")

        return redirect(url_for("mod_users"))

    reason = request.form.get("reason", "").strip() or "не указана"

    conn = get_db()

    conn.execute("UPDATE users SET is_banned=1, ban_reason=? WHERE id=?", (reason, uid))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "ban_user", f"user #{uid}: {reason}")

    flash("Пользователь забанен", "ok")

    return redirect(url_for("mod_users"))





@app.route("/mod/users/<int:uid>/unban", methods=["POST"])

@role_required("moderator")

def mod_unban(uid):

    me = current_user()

    conn = get_db()

    conn.execute("UPDATE users SET is_banned=0, ban_reason='' WHERE id=?", (uid,))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "unban_user", f"user #{uid}")

    flash("Пользователь разбанен", "ok")

    return redirect(url_for("mod_users"))





@app.route("/mod/users/<int:uid>/delete", methods=["POST"])

@role_required("moderator")

def mod_delete_user(uid):

    me = current_user()

    if uid == me["id"]:

        flash("Нельзя удалить себя", "error")

        return redirect(url_for("mod_users"))

    conn = get_db()

    conn.execute("DELETE FROM users WHERE id=?", (uid,))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "delete_user", f"user #{uid}")

    flash("Пользователь удалён", "ok")

    return redirect(url_for("mod_users"))





@app.route("/mod/reviews")

@role_required("moderator")

def mod_reviews():

    conn = get_db()

    rows = conn.execute(

        "SELECT r.*, u.username AS author FROM reviews r JOIN users u ON u.id=r.author_id "

        "ORDER BY r.created_at DESC"

    ).fetchall()

    conn.close()

    return render_template("mod/reviews.html", reviews=rows)





@app.route("/mod/reviews/<int:rid>/toggle_hidden", methods=["POST"])

@role_required("moderator")

def mod_toggle_hidden(rid):

    me = current_user()

    conn = get_db()

    r = conn.execute("SELECT is_hidden FROM reviews WHERE id=?", (rid,)).fetchone()

    if r:

        new_val = 0 if r["is_hidden"] else 1

        conn.execute("UPDATE reviews SET is_hidden=? WHERE id=?", (new_val, rid))

        conn.commit()

        log_mod_action(me["id"], "toggle_hide_review", f"review #{rid} -> hidden={new_val}")

    conn.close()

    return redirect(request.referrer or url_for("mod_reviews"))





@app.route("/mod/reviews/<int:rid>/toggle_featured", methods=["POST"])

@role_required("moderator")

def mod_toggle_featured(rid):

    me = current_user()

    conn = get_db()

    r = conn.execute("SELECT is_featured FROM reviews WHERE id=?", (rid,)).fetchone()

    if r:

        new_val = 0 if r["is_featured"] else 1

        conn.execute("UPDATE reviews SET is_featured=? WHERE id=?", (new_val, rid))

        conn.commit()

        log_mod_action(me["id"], "toggle_featured_review", f"review #{rid} -> featured={new_val}")

    conn.close()

    return redirect(request.referrer or url_for("mod_reviews"))





@app.route("/mod/reviews/<int:rid>/sotd", methods=["POST"])

@role_required("moderator")

def mod_set_sotd(rid):

    me = current_user()

    note = request.form.get("note", "").strip()[:300]

    conn = get_db()

    r = conn.execute("SELECT id FROM reviews WHERE id=?", (rid,)).fetchone()

    if r:

        conn.execute(

            "INSERT INTO song_of_day(review_id,note,set_at,set_by) VALUES (?,?,?,?)",

            (rid, note, datetime.utcnow().isoformat(), me["id"]),

        )

        conn.commit()

        log_mod_action(me["id"], "set_sotd", f"review #{rid}")

        flash("Назначено как «альбом дня»", "ok")

    conn.close()

    return redirect(url_for("mod_reviews"))





@app.route("/mod/comments")

@role_required("moderator")

def mod_comments():

    conn = get_db()

    rows = conn.execute(

        "SELECT c.*, u.username AS author, r.artist, r.title "

        "FROM comments c JOIN users u ON u.id=c.author_id "

        "JOIN reviews r ON r.id=c.review_id ORDER BY c.created_at DESC LIMIT 200"

    ).fetchall()

    conn.close()

    return render_template("mod/comments.html", comments=rows)





@app.route("/mod/reports")

@role_required("moderator")

def mod_reports():

    conn = get_db()

    rows = conn.execute(

        "SELECT rp.*, u.username AS reporter FROM reports rp JOIN users u ON u.id=rp.reporter_id "

        "ORDER BY rp.status='open' DESC, rp.created_at DESC"

    ).fetchall()

    conn.close()

    return render_template("mod/reports.html", reports=rows)





@app.route("/mod/reports/<int:rid>/resolve", methods=["POST"])

@role_required("moderator")

def mod_report_resolve(rid):

    me = current_user()

    resolution = request.form.get("resolution", "").strip() or "решено"

    conn = get_db()

    conn.execute(

        "UPDATE reports SET status='resolved', handler_id=?, resolution=?, resolved_at=? WHERE id=?",

        (me["id"], resolution, datetime.utcnow().isoformat(), rid),

    )

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "resolve_report", f"report #{rid}: {resolution}")

    flash("Жалоба закрыта", "ok")

    return redirect(url_for("mod_reports"))





@app.route("/mod/logs")

@role_required("moderator")

def mod_logs():

    conn = get_db()

    rows = conn.execute(

        "SELECT l.*, u.username FROM mod_log l JOIN users u ON u.id=l.moderator_id "

        "ORDER BY l.created_at DESC LIMIT 500"

    ).fetchall()

    conn.close()

    return render_template("mod/logs.html", logs=rows)





@app.route("/mod/stats")

@role_required("moderator")

def mod_stats():

    conn = get_db()

    role_breakdown = conn.execute(

        "SELECT role, COUNT(*) AS c FROM users GROUP BY role"

    ).fetchall()

    genre_breakdown = conn.execute(

        "SELECT genre, COUNT(*) AS c FROM reviews WHERE genre<>'' GROUP BY genre ORDER BY c DESC"

    ).fetchall()

    top_authors = conn.execute(

        "SELECT u.username, COUNT(r.id) AS c FROM users u LEFT JOIN reviews r ON r.author_id=u.id "

        "GROUP BY u.id ORDER BY c DESC LIMIT 10"

    ).fetchall()

    conn.close()

    return render_template(

        "mod/stats.html",

        roles=role_breakdown, genres=genre_breakdown, authors=top_authors,

        visits=get_visits(),

    )





@app.route("/mod/settings", methods=["GET", "POST"])

@role_required("moderator")

def mod_settings():

    me = current_user()

    if request.method == "POST":

        keys = ["site_banner", "registration_open", "guestbook_open", "moderator_motd",

                "site_tagline", "site_quote"]

        for k in keys:

            if k in request.form:

                set_setting(k, request.form.get(k, "").strip())

        log_mod_action(me["id"], "update_settings", "site settings")

        flash("Настройки сохранены", "ok")

        return redirect(url_for("mod_settings"))

    conn = get_db()

    words = conn.execute("SELECT * FROM banned_words ORDER BY word").fetchall()

    conn.close()

    return render_template(

        "mod/settings.html",

        banner=get_setting("site_banner", ""),

        tagline=get_setting("site_tagline", ""),

        quote=get_setting("site_quote", ""),

        registration_open=get_setting("registration_open", "1"),

        guestbook_open=get_setting("guestbook_open", "1"),

        motd=get_setting("moderator_motd", ""),

        words=words,

    )





@app.route("/mod/words/add", methods=["POST"])

@role_required("moderator")

def mod_words_add():

    me = current_user()

    w = request.form.get("word", "").strip().lower()

    if w:

        conn = get_db()

        conn.execute("INSERT OR IGNORE INTO banned_words(word) VALUES (?)", (w,))

        conn.commit()

        conn.close()

        log_mod_action(me["id"], "add_banned_word", w)

    return redirect(url_for("mod_settings"))





@app.route("/mod/words/<int:wid>/delete", methods=["POST"])

@role_required("moderator")

def mod_words_delete(wid):

    me = current_user()

    conn = get_db()

    conn.execute("DELETE FROM banned_words WHERE id=?", (wid,))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "remove_banned_word", str(wid))

    return redirect(url_for("mod_settings"))





@app.route("/mod/guestbook/<int:gid>/toggle", methods=["POST"])

@role_required("moderator")

def mod_guestbook_toggle(gid):

    me = current_user()

    conn = get_db()

    g = conn.execute("SELECT is_hidden FROM guestbook WHERE id=?", (gid,)).fetchone()

    if g:

        new_val = 0 if g["is_hidden"] else 1

        conn.execute("UPDATE guestbook SET is_hidden=? WHERE id=?", (new_val, gid))

        conn.commit()

        log_mod_action(me["id"], "toggle_guestbook", f"#{gid} hidden={new_val}")

    conn.close()

    return redirect(url_for("guestbook"))









@app.route("/mod/events", methods=["GET", "POST"])

@role_required("moderator")

def mod_events():

    me = current_user()

    if request.method == "POST":

        title = request.form.get("title", "").strip()[:120]

        description = request.form.get("description", "").strip()[:1500]

        city = request.form.get("city", "").strip()[:60]

        venue = request.form.get("venue", "").strip()[:120]

        starts_at = request.form.get("starts_at", "").strip()

        link = request.form.get("link", "").strip()[:300]

        emoji = (request.form.get("cover_emoji", "🎤") or "🎤")[:6]

        if title and starts_at:

            try:

                datetime.fromisoformat(starts_at.replace(" ", "T"))

                starts_iso = starts_at.replace(" ", "T")

            except Exception:

                flash("Дата некорректна (нужно YYYY-MM-DDTHH:MM)", "error")

                return redirect(url_for("mod_events"))

            conn = get_db()

            conn.execute(

                "INSERT INTO events(title,description,city,venue,starts_at,link,cover_emoji,"

                "created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)",

                (title, description, city, venue, starts_iso, link, emoji, me["id"],

                 datetime.utcnow().isoformat()),

            )

            conn.commit()

            conn.close()

            log_mod_action(me["id"], "create_event", title)

            flash("Событие добавлено", "ok")

        else:

            flash("Заполните название и дату", "error")

        return redirect(url_for("mod_events"))

    conn = get_db()

    rows = conn.execute("SELECT * FROM events ORDER BY starts_at DESC").fetchall()

    conn.close()

    return render_template("mod/events.html", events=rows)





@app.route("/mod/events/<int:eid>/toggle", methods=["POST"])

@role_required("moderator")

def mod_event_toggle(eid):

    me = current_user()

    conn = get_db()

    e = conn.execute("SELECT is_hidden FROM events WHERE id=?", (eid,)).fetchone()

    if e:

        nv = 0 if e["is_hidden"] else 1

        conn.execute("UPDATE events SET is_hidden=? WHERE id=?", (nv, eid))

        conn.commit()

        log_mod_action(me["id"], "toggle_event", f"#{eid} hidden={nv}")

    conn.close()

    return redirect(url_for("mod_events"))





@app.route("/mod/events/<int:eid>/delete", methods=["POST"])

@role_required("moderator")

def mod_event_delete(eid):

    me = current_user()

    conn = get_db()

    conn.execute("DELETE FROM events WHERE id=?", (eid,))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "delete_event", f"#{eid}")

    return redirect(url_for("mod_events"))









@app.route("/mod/polls", methods=["GET", "POST"])

@role_required("moderator")

def mod_polls():

    me = current_user()

    if request.method == "POST":

        question = request.form.get("question", "").strip()[:200]

        options_raw = request.form.get("options", "").strip()

        options = [o.strip()[:80] for o in options_raw.split("\n") if o.strip()]

        if not question or len(options) < 2:

            flash("Нужны вопрос и хотя бы 2 варианта", "error")

            return redirect(url_for("mod_polls"))

        conn = get_db()

        cur = conn.execute(

            "INSERT INTO polls(question,created_by,created_at) VALUES (?,?,?)",

            (question, me["id"], datetime.utcnow().isoformat()),

        )

        pid = cur.lastrowid

        for o in options[:8]:

            conn.execute("INSERT INTO poll_options(poll_id,text) VALUES (?,?)", (pid, o))

        conn.commit()

        conn.close()

        log_mod_action(me["id"], "create_poll", question)

        flash("Опрос создан", "ok")

        return redirect(url_for("mod_polls"))

    conn = get_db()

    rows = conn.execute(

        "SELECT p.*, "

        "(SELECT COUNT(*) FROM poll_votes WHERE poll_id=p.id) AS vc "

        "FROM polls p ORDER BY created_at DESC"

    ).fetchall()

    conn.close()

    return render_template("mod/polls.html", polls=rows)





@app.route("/mod/polls/<int:pid>/toggle_close", methods=["POST"])

@role_required("moderator")

def mod_poll_toggle_close(pid):

    me = current_user()

    conn = get_db()

    p = conn.execute("SELECT is_closed FROM polls WHERE id=?", (pid,)).fetchone()

    if p:

        nv = 0 if p["is_closed"] else 1

        conn.execute("UPDATE polls SET is_closed=? WHERE id=?", (nv, pid))

        conn.commit()

        log_mod_action(me["id"], "toggle_poll_close", f"#{pid} closed={nv}")

    conn.close()

    return redirect(url_for("mod_polls"))





@app.route("/mod/polls/<int:pid>/delete", methods=["POST"])

@role_required("moderator")

def mod_poll_delete(pid):

    me = current_user()

    conn = get_db()

    conn.execute("DELETE FROM polls WHERE id=?", (pid,))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "delete_poll", f"#{pid}")

    return redirect(url_for("mod_polls"))









@app.route("/mod/challenges", methods=["GET", "POST"])

@role_required("moderator")

def mod_challenges():

    me = current_user()

    if request.method == "POST":

        title = request.form.get("title", "").strip()[:120]

        description = request.form.get("description", "").strip()[:1500]

        starts_at = request.form.get("starts_at", "").strip()

        ends_at = request.form.get("ends_at", "").strip()

        if not title or not starts_at or not ends_at:

            flash("Заполните название и даты", "error")

            return redirect(url_for("mod_challenges"))

        try:

            starts_iso = starts_at.replace(" ", "T")

            ends_iso = ends_at.replace(" ", "T")

            datetime.fromisoformat(starts_iso)

            datetime.fromisoformat(ends_iso)

        except Exception:

            flash("Дата некорректна", "error")

            return redirect(url_for("mod_challenges"))

        conn = get_db()

        conn.execute(

            "INSERT INTO challenges(title,description,starts_at,ends_at,created_by,created_at) "

            "VALUES (?,?,?,?,?,?)",

            (title, description, starts_iso, ends_iso, me["id"], datetime.utcnow().isoformat()),

        )

        conn.commit()

        conn.close()

        log_mod_action(me["id"], "create_challenge", title)

        flash("Челлендж создан", "ok")

        return redirect(url_for("mod_challenges"))

    conn = get_db()

    rows = conn.execute(

        "SELECT c.*, "

        "(SELECT COUNT(*) FROM challenge_submissions WHERE challenge_id=c.id) AS sc "

        "FROM challenges c ORDER BY ends_at DESC"

    ).fetchall()

    conn.close()

    return render_template("mod/challenges.html", challenges=rows)





@app.route("/mod/challenges/<int:cid>/toggle", methods=["POST"])

@role_required("moderator")

def mod_challenge_toggle(cid):

    me = current_user()

    conn = get_db()

    c = conn.execute("SELECT is_hidden FROM challenges WHERE id=?", (cid,)).fetchone()

    if c:

        nv = 0 if c["is_hidden"] else 1

        conn.execute("UPDATE challenges SET is_hidden=? WHERE id=?", (nv, cid))

        conn.commit()

        log_mod_action(me["id"], "toggle_challenge", f"#{cid} hidden={nv}")

    conn.close()

    return redirect(url_for("mod_challenges"))





@app.route("/mod/challenges/<int:cid>/delete", methods=["POST"])

@role_required("moderator")

def mod_challenge_delete(cid):

    me = current_user()

    conn = get_db()

    conn.execute("DELETE FROM challenges WHERE id=?", (cid,))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "delete_challenge", f"#{cid}")

    return redirect(url_for("mod_challenges"))









@app.route("/mod/quotes", methods=["GET", "POST"])

@role_required("moderator")

def mod_quotes():

    me = current_user()

    if request.method == "POST":

        text = request.form.get("text", "").strip()[:300]

        artist = request.form.get("artist", "").strip()[:100]

        song = request.form.get("song", "").strip()[:100]

        if text:

            conn = get_db()

            conn.execute(

                "INSERT INTO lyrics_quotes(text,artist,song,submitted_by,created_at) "

                "VALUES (?,?,?,?,?)",

                (text, artist, song, me["id"], datetime.utcnow().isoformat()),

            )

            conn.commit()

            conn.close()

            log_mod_action(me["id"], "add_quote", artist or "—")

            flash("Цитата добавлена", "ok")

        return redirect(url_for("mod_quotes"))

    conn = get_db()

    rows = conn.execute(

        "SELECT q.*, u.username AS submitter FROM lyrics_quotes q "

        "LEFT JOIN users u ON u.id=q.submitted_by ORDER BY q.created_at DESC"

    ).fetchall()

    conn.close()

    return render_template("mod/quotes.html", quotes=rows)





@app.route("/mod/quotes/<int:qid>/toggle", methods=["POST"])

@role_required("moderator")

def mod_quote_toggle(qid):

    me = current_user()

    conn = get_db()

    q = conn.execute("SELECT is_hidden FROM lyrics_quotes WHERE id=?", (qid,)).fetchone()

    if q:

        nv = 0 if q["is_hidden"] else 1

        conn.execute("UPDATE lyrics_quotes SET is_hidden=? WHERE id=?", (nv, qid))

        conn.commit()

        log_mod_action(me["id"], "toggle_quote", f"#{qid} hidden={nv}")

    conn.close()

    return redirect(url_for("mod_quotes"))





@app.route("/mod/quotes/<int:qid>/delete", methods=["POST"])

@role_required("moderator")

def mod_quote_delete(qid):

    me = current_user()

    conn = get_db()

    conn.execute("DELETE FROM lyrics_quotes WHERE id=?", (qid,))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "delete_quote", f"#{qid}")

    return redirect(url_for("mod_quotes"))









@app.route("/mod/quiz", methods=["GET", "POST"])

@role_required("moderator")

def mod_quiz():

    me = current_user()

    if request.method == "POST":

        question = request.form.get("question", "").strip()[:300]

        opts_raw = request.form.get("options", "").strip()

        try:

            correct = int(request.form.get("correct", "0"))

        except ValueError:

            correct = 0

        explanation = request.form.get("explanation", "").strip()[:300]

        opts = [o.strip()[:120] for o in opts_raw.split("\n") if o.strip()]

        if not question or len(opts) < 2:

            flash("Вопрос и минимум 2 варианта", "error")

            return redirect(url_for("mod_quiz"))

        if correct < 0 or correct >= len(opts):

            flash("Некорректный номер правильного ответа", "error")

            return redirect(url_for("mod_quiz"))

        conn = get_db()

        conn.execute(

            "INSERT INTO quiz_questions(question,options,correct,explanation,created_at) "

            "VALUES (?,?,?,?,?)",

            (question, "|".join(opts), correct, explanation, datetime.utcnow().isoformat()),

        )

        conn.commit()

        conn.close()

        log_mod_action(me["id"], "add_quiz", question[:60])

        flash("Вопрос добавлен", "ok")

        return redirect(url_for("mod_quiz"))

    conn = get_db()

    rows = conn.execute("SELECT * FROM quiz_questions ORDER BY created_at DESC").fetchall()

    conn.close()

    return render_template("mod/quiz.html", questions=rows)





@app.route("/mod/quiz/<int:qid>/delete", methods=["POST"])

@role_required("moderator")

def mod_quiz_delete(qid):

    me = current_user()

    conn = get_db()

    conn.execute("DELETE FROM quiz_questions WHERE id=?", (qid,))

    conn.commit()

    conn.close()

    log_mod_action(me["id"], "delete_quiz", f"#{qid}")

    return redirect(url_for("mod_quiz"))









@app.route("/mod/playlists")

@role_required("moderator")

def mod_playlists():

    conn = get_db()

    rows = conn.execute(

        "SELECT p.*, u.username AS owner, "

        "(SELECT COUNT(*) FROM playlist_items WHERE playlist_id=p.id) AS n "

        "FROM playlists p JOIN users u ON u.id=p.owner_id ORDER BY created_at DESC"

    ).fetchall()

    conn.close()

    return render_template("mod/playlists.html", playlists=rows)





@app.route("/mod/playlists/<int:pid>/toggle", methods=["POST"])

@role_required("moderator")

def mod_playlist_toggle(pid):

    me = current_user()

    conn = get_db()

    p = conn.execute("SELECT is_hidden FROM playlists WHERE id=?", (pid,)).fetchone()

    if p:

        nv = 0 if p["is_hidden"] else 1

        conn.execute("UPDATE playlists SET is_hidden=? WHERE id=?", (nv, pid))

        conn.commit()

        log_mod_action(me["id"], "toggle_playlist", f"#{pid} hidden={nv}")

    conn.close()

    return redirect(url_for("mod_playlists"))









@app.route("/api/health")

def api_health():

    return jsonify({"status": "ok", "app": "Music_Thoughts", "version": "3.0"})





@app.route("/api/reviews")

def api_reviews():

    conn = get_db()

    rows = conn.execute(

        "SELECT r.id, r.artist, r.title, r.genre, r.year, r.score, r.created_at, "

        "u.username AS author FROM reviews r JOIN users u ON u.id=r.author_id "

        "WHERE r.is_hidden=0 AND r.is_draft=0 ORDER BY r.created_at DESC LIMIT 100"

    ).fetchall()

    conn.close()

    return jsonify([dict(r) for r in rows])





@app.route("/api/review/<int:rid>")

def api_review(rid):

    conn = get_db()

    r = conn.execute(

        "SELECT r.*, u.username AS author FROM reviews r JOIN users u ON u.id=r.author_id "

        "WHERE r.id=? AND r.is_hidden=0 AND r.is_draft=0",

        (rid,),

    ).fetchone()

    conn.close()

    if not r:

        return jsonify({"error": "not found"}), 404

    d = dict(r)

    d["tags"] = get_review_tags(rid)

    return jsonify(d)





@app.route("/api/quote")

def api_quote():

    q = random_lyric_quote()

    if not q:

        return jsonify({"error": "no quotes"}), 404

    return jsonify({"text": q["text"], "artist": q["artist"], "song": q["song"]})





@app.route("/rss")

def rss():

    conn = get_db()

    rows = conn.execute(

        "SELECT r.*, u.username AS author FROM reviews r JOIN users u ON u.id=r.author_id "

        "WHERE r.is_hidden=0 AND r.is_draft=0 ORDER BY r.created_at DESC LIMIT 30"

    ).fetchall()

    conn.close()

    items = []

    for r in rows:

        link = url_for("review_detail", rid=r["id"], _external=True)

        items.append(f"""<item>
  <title>{r['artist']} — {r['title']} ({r['score']}/10)</title>
  <link>{link}</link>
  <pubDate>{r['created_at']}</pubDate>
  <description><![CDATA[{r['body'][:500]}]]></description>
  <author>{r['author']}</author>
</item>""")

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Music_Thoughts — рецензии</title>
<link>{url_for('index', _external=True)}</link>
<description>{get_setting('site_tagline', '')}</description>
{''.join(items)}
</channel></rss>"""

    return Response(body, mimetype="application/rss+xml")









@app.errorhandler(404)

def err404(e):

    return render_template("404.html", code=404, message="Страница не найдена"), 404





@app.errorhandler(403)

def err403(e):

    return render_template("404.html", code=403, message="Доступ запрещён"), 403





@app.errorhandler(500)

def err500(e):

    return render_template("404.html", code=500, message="Внутренняя ошибка"), 500









if __name__ == "__main__":

    import threading as _t

    from database import resolve_listen_urls as _resolve

    init_db()

    _t.Thread(target=_resolve, daemon=True).start()

    app.run(host="127.0.0.1", port=5000, debug=True)

