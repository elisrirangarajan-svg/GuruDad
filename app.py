"""
NoteBridge server.

Two jobs:
  1. Accept a photo upload from Dad's web page  -> POST /upload
  2. Let the Raspberry Pi ask "anything new?"    -> GET  /next
                                                  -> POST /mark_printed/<id>

Photos are stored as plain files on disk, with a small JSON file
acting as our "database" of what's been printed or not.
"""

import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
DB_FILE = "notes_db.json"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------- tiny "database" helpers ----------

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r") as f:
        return json.load(f)


def save_db(notes):
    with open(DB_FILE, "w") as f:
        json.dump(notes, f, indent=2)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------- routes ----------

@app.route("/")
def home():
    """The page Dad opens to send a note."""
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload():
    """Dad's page sends a photo here."""
    if "photo" not in request.files:
        return jsonify({"error": "No photo included in request"}), 400

    file = request.files["photo"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only png/jpg/jpeg files are allowed"}), 400

    # Give every upload a unique name so notes never overwrite each other
    extension = file.filename.rsplit(".", 1)[1].lower()
    note_id = str(uuid.uuid4())
    saved_filename = f"{note_id}.{extension}"
    filepath = os.path.join(UPLOAD_FOLDER, saved_filename)
    file.save(filepath)

    notes = load_db()
    notes.append({
        "id": note_id,
        "filename": saved_filename,
        "uploaded_at": datetime.utcnow().isoformat(),
        "printed": False
    })
    save_db(notes)

    return jsonify({"success": True, "id": note_id})


@app.route("/next", methods=["GET"])
def next_note():
    """The Pi calls this to ask: is there a note waiting to be printed?"""
    notes = load_db()
    for note in notes:
        if not note["printed"]:
            return jsonify({
                "id": note["id"],
                "image_url": f"/image/{note['filename']}"
            })
    return jsonify({"id": None})


@app.route("/image/<filename>")
def get_image(filename):
    """Lets the Pi download the actual image file."""
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/mark_printed/<note_id>", methods=["POST"])
def mark_printed(note_id):
    """The Pi calls this after it successfully prints a note."""
    notes = load_db()
    for note in notes:
        if note["id"] == note_id:
            note["printed"] = True
            save_db(notes)
            return jsonify({"success": True})
    return jsonify({"error": "Note not found"}), 404


if __name__ == "__main__":
    # debug=True is handy while building locally; turn this off when deployed
    app.run(host="0.0.0.0", port=5000, debug=False)
