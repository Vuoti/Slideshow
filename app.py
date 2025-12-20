import os
import json
import time
import threading
import logging
import uuid
import subprocess
import shutil
import cv2
import numpy as np
from flask import Flask, render_template, jsonify, request
from PIL import Image, ExifTags, ImageOps
from pillow_heif import register_heif_opener

# --- Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

register_heif_opener()

app = Flask(__name__)

IMAGE_FOLDER = os.path.join('static', 'images')
CROP_FILE = 'crops.json'
SETTINGS_FILE = 'settings.json' # Neu: Hier speichern wir Dauer & Modus
UPLOAD_SECRET = "oma-ist-die-beste"
CASCADE_PATH = "haarcascade_frontalface_default.xml"
FFMPEG_PATH = shutil.which('ffmpeg') or '/usr/bin/ffmpeg'

os.makedirs(IMAGE_FOLDER, exist_ok=True)

face_cascade = cv2.CascadeClassifier(CASCADE_PATH)

# --- Helper Funktionen ---

def load_json(filepath, default):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return default

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def detect_focus_point(image_path):
    # (Dieser Code bleibt unverändert wie vorher)
    try:
        pil_img = Image.open(image_path)
        pil_img = ImageOps.exif_transpose(pil_img)
        img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        if len(faces) > 0:
            x, y, w, h = faces[0]
            return round(((x + w // 2) / pil_img.size[0]) * 100), round(((y + h // 2) / pil_img.size[1]) * 100)
    except Exception as e:
        logger.error(f"Fehler bei Face Detection: {e}")
    return 50, 50

def worker_loop():
    # (Dieser Code bleibt unverändert wie vorher)
    while True:
        try:
            if os.path.exists(IMAGE_FOLDER):
                files = os.listdir(IMAGE_FOLDER)
                crops = load_json(CROP_FILE, {})
                crops_changed = False
                
                for filename in files:
                    file_path = os.path.join(IMAGE_FOLDER, filename)
                    name, ext = os.path.splitext(filename)
                    ext = ext.lower()
                    
                    if (time.time() - os.path.getmtime(file_path)) < 5: continue

                    if ext == '.heic':
                        target = os.path.join(IMAGE_FOLDER, name + ".converted.jpg")
                        if not os.path.exists(target):
                            try:
                                img = Image.open(file_path)
                                img = ImageOps.exif_transpose(img)
                                img.save(target, "JPEG", quality=90)
                            except: pass
                    elif ext in ['.mov', '.m4v', '.mkv', '.webm']:
                        target = os.path.join(IMAGE_FOLDER, name + ".converted.mp4")
                        if not os.path.exists(target):
                            subprocess.run([FFMPEG_PATH, '-i', file_path, '-vcodec', 'libx264', '-pix_fmt', 'yuv420p', '-vf', 'scale=1920:-2', '-acodec', 'aac', '-movflags', 'faststart', '-y', target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    if filename.endswith(('.jpg', '.jpeg', '.png', '.webp')) and filename not in crops:
                        px, py = detect_focus_point(file_path)
                        crops[filename] = {"x": px, "y": py}
                        crops_changed = True
                
                if crops_changed: save_json(CROP_FILE, crops)
        except Exception: pass
        time.sleep(10)

threading.Thread(target=worker_loop, daemon=True).start()

# --- Routen ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """Liest oder speichert die globalen Einstellungen"""
    # 1. Starten mit den vollen Standardwerten
    current_settings = {
        "duration": 10, 
        "mode": "slideshow",
        "newest_count": 5,
        "brightness": 100,
        "night_mode": False,
        "night_start": "22:00",
        "night_end": "07:00",
        "night_brightness": 20
    }
    
    # 2. Wenn Datei existiert, Werte laden und Defaults überschreiben
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            saved_data = json.load(f)
            current_settings.update(saved_data)
    
    if request.method == 'POST':
        # 3. Neue Werte vom Frontend übernehmen
        current_settings.update(request.json)
        save_json(SETTINGS_FILE, current_settings)
        return jsonify({"success": True})
        
    return jsonify(current_settings)

@app.route('/api/images')
def get_images():
    crops = load_json(CROP_FILE, {})
    media_list = []
    
    # Sortieren nach Datum (Neueste zuerst)
    files = sorted(os.listdir(IMAGE_FOLDER), key=lambda x: os.path.getmtime(os.path.join(IMAGE_FOLDER, x)), reverse=True)
    
    for filename in files:
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.webp', '.mp4']:
            crop_data = crops.get(filename, {"x": 50, "y": 50})
            media_list.append({
                "url": filename,
                "type": "video" if ext == '.mp4' else "image",
                "focus_x": crop_data['x'],
                "focus_y": crop_data['y']
            })
            
    return jsonify(media_list)

@app.route('/api/delete', methods=['POST'])
def delete_image():
    """Löscht ein Bild und dessen Crop-Daten"""
    filename = request.json.get('filename')
    if not filename: return jsonify({"error": "No filename"}), 400
    
    path = os.path.join(IMAGE_FOLDER, filename)
    
    # 1. Datei löschen
    if os.path.exists(path):
        os.remove(path)
    
    # 2. Falls es konvertierte Versionen gibt (z.B. das Original HEIC), auch löschen?
    # Das ist komplex. Wir löschen erstmal nur das angezeigte Bild.
    # Wenn wir aufräumen wollen, müssten wir auch nach .heic suchen mit gleichem Namen.
    base_name = filename.replace('.converted.jpg', '').replace('.converted.mp4', '').replace('.square.jpg', '')
    
    # Versuche Originale zu finden und zu löschen (Aufräumaktion)
    for f in os.listdir(IMAGE_FOLDER):
        if f.startswith(base_name) and f != filename:
            try:
                os.remove(os.path.join(IMAGE_FOLDER, f))
            except: pass

    # 3. Aus Crops entfernen
    crops = load_json(CROP_FILE, {})
    if filename in crops:
        del crops[filename]
        save_json(CROP_FILE, crops)
        
    return jsonify({"success": True})

@app.route('/api/update_crop', methods=['POST'])
def update_crop():
    data = request.json
    filename = data.get('filename')
    if filename and os.path.exists(os.path.join(IMAGE_FOLDER, filename)):
        crops = load_json(CROP_FILE, {})
        crops[filename] = {"x": data.get('x'), "y": data.get('y')}
        save_json(CROP_FILE, crops)
        return jsonify({"success": True})
    return jsonify({"error": "File not found"}), 404

@app.route('/api/upload', methods=['POST'])
def upload_image():
    # (Dieser Code bleibt unverändert)
    token = request.headers.get('X-Upload-Token')
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            if token and token != UPLOAD_SECRET:
                return jsonify({"error": "Wrong Token"}), 403
            unique_filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1].lower()
            file.save(os.path.join(IMAGE_FOLDER, unique_filename))
            return jsonify({"success": True, "filename": unique_filename})
    return jsonify({"error": "No file"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6001)