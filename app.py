import os
import threading
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, jsonify, abort

from db import init_db, get_conn, get_setting, set_setting
from utils import now_iso, ext_of, detect_mime, classify_by_ext, gen_stored_name, normalise_expiry_choice, safe_name



app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "Temp")

os.makedirs(TEMP_DIR, exist_ok=True)
init_db()

def get_max_file_bytes() -> int:
    return int(get_setting("max_file_bytes") or "0")

def parse_size(size: str, unit: str) -> int:
    size = float(size)

    unit = unit.lower()

    if unit == "mb":
        return int(size * 1024 * 1024)

    if unit == "gb":
        return int(size * 1024 * 1024 * 1024)

    raise ValueError("Invalid unit")
def get_used_bytes() -> int:
    conn = get_conn()
    row = conn.execute("SELECT COALESCE(SUM(size_bytes),0) AS used FROM files").fetchone()
    conn.close()
    return int(row["used"])

def get_quota_bytes() -> int:
    return int(get_setting("quota_bytes"))

def uploads_allowed() -> bool:
    # 規則 1：配額可以調小到低於已用，此時只允許下載，不允許上傳
    return get_used_bytes() <= get_quota_bytes()

def cleanup_expired():
    """
    刪除已過期且非永久的文件：DB + 磁碟文件
    """
    conn = get_conn()
    rows = conn.execute("""
      SELECT id, stored_name FROM files
      WHERE is_forever=0 AND expires_at IS NOT NULL AND expires_at <= ?
    """, (now_iso(),)).fetchall()

    for r in rows:
        path = os.path.join(TEMP_DIR, r["stored_name"])
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        conn.execute("DELETE FROM files WHERE id=?", (r["id"],))
    conn.commit()
    conn.close()

def start_cleanup_loop():
    def loop():
        try:
            cleanup_expired()
        finally:
            interval = int(get_setting("cleanup_interval_seconds") or "60")
            t = threading.Timer(interval, loop)
            t.daemon = True
            t.start()
    loop()

start_cleanup_loop()

@app.get("/")
def index():
    cleanup_expired()
    cat = request.args.get("cat", "all")
    conn = get_conn()

    if cat == "all":
        rows = conn.execute("SELECT * FROM files ORDER BY id DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM files WHERE category=? ORDER BY id DESC", (cat,)).fetchall()

    conn.close()

    quota = get_quota_bytes()
    used = get_used_bytes()
    return render_template(
        "index.html",
        files=rows,
        cat=cat,
        quota=quota,
        used=used,
        can_upload=uploads_allowed(),
    )

@app.post("/upload")
def upload():
    cleanup_expired()

    # 下载模式禁止上传
    if not uploads_allowed():
        return jsonify({
            "ok": False,
            "msg": "Uploads disabled (download-only mode)."
        }), 403

    expiry_choice = request.form.get("expiry", "7")
    is_forever, expires_at = normalise_expiry_choice(expiry_choice)

    uploaded = request.files.getlist("files")

    if not uploaded:
        return jsonify({"ok": False, "msg": "No files uploaded."}), 400


    quota = get_quota_bytes()
    used = get_used_bytes()
    max_file = get_max_file_bytes()

    total_new = 0


    # ========= 第一轮：大小检测 =========
    for f in uploaded:

        f.stream.seek(0, os.SEEK_END)
        size = f.stream.tell()
        f.stream.seek(0)

        # 单文件限制
        if max_file > 0 and size > max_file:
            return jsonify({
                "ok": False,
                "msg": f"File '{f.filename}' exceeds single-file limit."
            }), 413

        total_new += size


    # ========= 总容量检测 =========
    if used + total_new > quota:
        return jsonify({
            "ok": False,
            "msg": "Storage quota exceeded."
        }), 413


    # ========= 保存 =========
    conn = get_conn()
    saved = 0

    for f in uploaded:

        orig = f.filename or "file"

        ext = ext_of(orig)  # 永远从原始名取后缀

        if not ext:
            ext = ""

        stored = gen_stored_name(orig)

        orig_safe = safe_name(orig)
        mime = detect_mime(orig_safe)
        category = classify_by_ext(ext)

        path = os.path.join(TEMP_DIR, stored)

        f.save(path)

        size = os.path.getsize(path)

        conn.execute("""
          INSERT INTO files
          (orig_name, stored_name, ext, mime, category,
           size_bytes, uploaded_at, expires_at, is_forever)

          VALUES(?,?,?,?,?,?,?,?,?)
        """, (
            orig,
            stored,
            ext,
            mime,
            category,
            size,
            now_iso(),
            expires_at,
            is_forever
        ))

        saved += 1


    conn.commit()
    conn.close()

    return jsonify({"ok": True, "saved": saved})

@app.get("/download/<int:file_id>")
def download(file_id: int):
    cleanup_expired()
    conn = get_conn()
    row = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
    if not row:
        conn.close()
        abort(404)

    conn.execute("UPDATE files SET downloads = downloads + 1 WHERE id=?", (file_id,))
    conn.commit()
    conn.close()

    return send_from_directory(TEMP_DIR, row["stored_name"], as_attachment=True, download_name=row["orig_name"])

@app.post("/files/<int:file_id>/expiry")
def set_expiry(file_id: int):
    choice = request.form.get("expiry")
    if not choice:
        return jsonify({"ok": False, "msg": "Missing expiry."}), 400
    is_forever, expires_at = normalise_expiry_choice(choice)

    conn = get_conn()
    conn.execute("UPDATE files SET is_forever=?, expires_at=? WHERE id=?", (is_forever, expires_at, file_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.post("/settings/quota")
def set_quota():
    quota_gb = request.form.get("quota_gb")
    if not quota_gb:
        return jsonify({"ok": False, "msg": "Missing quota_gb"}), 400
    try:
        gb = float(quota_gb)
        quota_bytes = int(gb * 1024 * 1024 * 1024)
        if quota_bytes <= 0:
            raise ValueError
    except ValueError:
        return jsonify({"ok": False, "msg": "Invalid quota value."}), 400

    set_setting("quota_bytes", str(quota_bytes))
    return jsonify({"ok": True, "used": get_used_bytes(), "quota": quota_bytes, "can_upload": uploads_allowed()})

@app.get("/settings/storage")
def get_storage_settings():

    quota = int(get_setting("quota_bytes") or "0")
    max_file = int(get_setting("max_file_bytes") or "0")

    return jsonify({
        "quota_bytes": quota,
        "max_file_bytes": max_file,
        "used_bytes": get_used_bytes(),
        "can_upload": uploads_allowed()
    })

@app.post("/settings/storage")
def set_storage_settings():

    try:
        quota_size = request.form.get("quota_size")
        quota_unit = request.form.get("quota_unit")

        file_size = request.form.get("file_size")
        file_unit = request.form.get("file_unit")

        if not all([quota_size, quota_unit, file_size, file_unit]):
            raise ValueError("Missing fields")

        quota_bytes = parse_size(quota_size, quota_unit)
        file_bytes = parse_size(file_size, file_unit)

        if quota_bytes <= 0 or file_bytes <= 0:
            raise ValueError("Invalid size")

    except Exception:
        return jsonify({
            "ok": False,
            "msg": "Invalid parameters."
        }), 400


    set_setting("quota_bytes", str(quota_bytes))
    set_setting("max_file_bytes", str(file_bytes))

    return jsonify({
        "ok": True,
        "quota_bytes": quota_bytes,
        "max_file_bytes": file_bytes,
        "can_upload": uploads_allowed()
    })

@app.before_request
def limit_request_size():

    if request.method == "POST" and request.path == "/upload":

        max_req = int(get_setting("max_request_bytes") or "0")

        length = request.content_length

        if max_req > 0 and length and length > max_req:

            return jsonify({
                "ok": False,
                "msg": "Request size exceeds server limit."
            }), 413

@app.post("/files/<int:file_id>/delete")
def delete_file(file_id: int):
    cleanup_expired()

    conn = get_conn()
    row = conn.execute("SELECT stored_name FROM files WHERE id=?", (file_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "msg": "File not found."}), 404

    stored_name = row["stored_name"]

    # 先删磁盘文件（即便失败也继续删 DB，避免“幽灵记录”）
    path = os.path.join(TEMP_DIR, stored_name)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        # 这里不抛错，给前端一个提示即可
        pass

    conn.execute("DELETE FROM files WHERE id=?", (file_id,))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})

@app.post("/cleanup")
def manual_cleanup():
    cleanup_expired()
    return jsonify({"ok": True})

if __name__ == "__main__":
    # 局域網訪問關鍵：0.0.0.0
    app.run(host="0.0.0.0", port=5000, debug=True)