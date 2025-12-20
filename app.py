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

# HEIC Support aktivieren
register_heif_opener()

app = Flask(__name__)

IMAGE_FOLDER = os.path.join('static', 'images')
CROP_FILE = 'crops.json'
UPLOAD_SECRET = "oma-ist-die-beste"
CASCADE_PATH = "haarcascade_frontalface_default.xml"
FFMPEG_PATH = shutil.which('ffmpeg') or '/usr/bin/ffmpeg' # Sucht FFmpeg automatisch

os.makedirs(IMAGE_FOLDER, exist_ok=True)

# Face Detector laden
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)

def load_crops():
    if os.path.exists(CROP_FILE):
        with open(CROP_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_crops(data):
    with open(CROP_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def detect_focus_point(image_path):
    """Sucht Gesicht und gibt x/y in Prozent zurück"""
    try:
        pil_img = Image.open(image_path)
        # Exif Rotation korrigieren, damit Oben auch Oben ist
        pil_img = ImageOps.exif_transpose(pil_img)
        
        img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) > 0:
            x, y, w, h = faces[0]
            center_x = x + w // 2
            center_y = y + h // 2
            
            width, height = pil_img.size
            return round((center_x / width) * 100), round((center_y / height) * 100)
            
    except Exception as e:
        logger.error(f"Fehler bei Face Detection ({image_path}): {e}")
    
    return 50, 50

def worker_loop():
    """
    Dieser Thread macht beides:
    1. Konvertieren (HEIC -> JPG, MOV -> MP4)
    2. Scannen (Gesichter finden in den fertigen JPGs)
    """
    while True:
        try:
            if os.path.exists(IMAGE_FOLDER):
                files = os.listdir(IMAGE_FOLDER)
                crops = load_crops()
                crops_changed = False

                for filename in files:
                    file_path = os.path.join(IMAGE_FOLDER, filename)
                    name, ext = os.path.splitext(filename)
                    ext = ext.lower()

                    # Datei warten lassen, falls Upload noch läuft (5 Sek Puffer)
                    if (time.time() - os.path.getmtime(file_path)) < 5:
                        continue

                    # --- TEIL 1: KONVERTIERUNG ---
                    
                    # A) HEIC zu JPG
                    if ext == '.heic':
                        target = os.path.join(IMAGE_FOLDER, name + ".converted.jpg")
                        if not os.path.exists(target):
                            logger.info(f"Konvertiere HEIC: {filename}")
                            try:
                                img = Image.open(file_path)
                                img = ImageOps.exif_transpose(img) # Rotation fixen
                                img.save(target, "JPEG", quality=90)
                            except Exception as e:
                                logger.error(f"Fehler HEIC: {e}")

                    # B) MOV/MKV zu MP4
                    elif ext in ['.mov', '.m4v', '.mkv', '.webm']:
                        target = os.path.join(IMAGE_FOLDER, name + ".converted.mp4")
                        if not os.path.exists(target):
                            logger.info(f"Konvertiere Video: {filename}")
                            cmd = [
                                FFMPEG_PATH, '-i', file_path, 
                                '-vcodec', 'libx264', '-pix_fmt', 'yuv420p', 
                                '-vf', 'scale=1920:-2', '-acodec', 'aac', 
                                '-movflags', 'faststart', '-y', target
                            ]
                            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


                    # --- TEIL 2: GESICHTER SCANNEN ---
                    # Wir scannen nur web-freundliche Bilder (auch die gerade konvertierten!)
                    if filename.endswith(('.jpg', '.jpeg', '.png', '.webp')) and filename not in crops:
                        logger.info(f"Scanne Fokus für: {filename}")
                        px, py = detect_focus_point(file_path)
                        crops[filename] = {"x": px, "y": py}
                        crops_changed = True
                
                if crops_changed:
                    save_crops(crops)

        except Exception as e:
            logger.error(f"Fehler im Worker Loop: {e}")
        
        time.sleep(10)

# Thread starten
threading.Thread(target=worker_loop, daemon=True).start()


# --- Routen ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/images')
def get_images():
    crops = load_crops()
    media_list = []
    
    # Sortieren nach Datum
    files = sorted(os.listdir(IMAGE_FOLDER), key=lambda x: os.path.getmtime(os.path.join(IMAGE_FOLDER, x)), reverse=True)
    
    for filename in files:
        ext = os.path.splitext(filename)[1].lower()
        
        # WICHTIG: Wir zeigen nur Web-Formate an!
        # Keine HEICs und keine MOVs in der Liste.
        # Die konvertierten Versionen (enden auf .jpg / .mp4) rutschen hier automatisch durch.
        if ext in ['.jpg', '.jpeg', '.png', '.webp', '.mp4']:
            
            # Crop Daten holen (Default: Mitte)
            crop_data = crops.get(filename, {"x": 50, "y": 50})
            
            item = {
                "url": filename,
                "type": "video" if ext == '.mp4' else "image",
                "focus_x": crop_data['x'],
                "focus_y": crop_data['y']
            }
            media_list.append(item)
            
    return jsonify(media_list)

@app.route('/api/update_crop', methods=['POST'])
def update_crop():
    data = request.json
    filename = data.get('filename')
    # Validierung: Nur speichern, wenn Datei existiert
    if filename and os.path.exists(os.path.join(IMAGE_FOLDER, filename)):
        crops = load_crops()
        crops[filename] = {"x": data.get('x'), "y": data.get('y')}
        save_crops(crops)
        return jsonify({"success": True})
    return jsonify({"error": "File not found"}), 404

@app.route('/api/upload', methods=['POST'])
def upload_image():
    # Token Prüfung für iOS Shortcut (optional für Admin)
    token = request.headers.get('X-Upload-Token')
    
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            # Token Check nur wenn Header gesetzt (für Shortcut Sicherheit)
            if token and token != UPLOAD_SECRET:
                return jsonify({"error": "Wrong Token"}), 403
                
            unique_filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1].lower()
            file.save(os.path.join(IMAGE_FOLDER, unique_filename))
            return jsonify({"success": True, "filename": unique_filename})
            
    return jsonify({"error": "No file"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6001)