import os
import time
import threading
import uuid
import subprocess
from flask import Flask, render_template, jsonify, request
from PIL import Image
from pillow_heif import register_heif_opener

# Damit Pillow HEIC lesen kann
register_heif_opener()

app = Flask(__name__)

IMAGE_FOLDER = os.path.join('static', 'images')
UPLOAD_SECRET = "oma-ist-die-beste"

os.makedirs(IMAGE_FOLDER, exist_ok=True)

def convert_media():
    """
    Läuft im Hintergrund und sucht nach HEIC oder MOV/HEVC Dateien
    und erstellt web-freundliche Kopien (JPG/MP4).
    """
    while True:
        try:
            if os.path.exists(IMAGE_FOLDER):
                for filename in os.listdir(IMAGE_FOLDER):
                    file_path = os.path.join(IMAGE_FOLDER, filename)
                    name, ext = os.path.splitext(filename)
                    ext = ext.lower()

                    # 1. HEIC zu JPG konvertieren
                    if ext == '.heic':
                        target_file = os.path.join(IMAGE_FOLDER, name + ".converted.jpg")
                        if not os.path.exists(target_file):
                            print(f"Konvertiere HEIC: {filename}")
                            try:
                                img = Image.open(file_path)
                                img.save(target_file, "JPEG", quality=90)
                            except Exception as e:
                                print(f"Fehler bei {filename}: {e}")

                    # 2. MOV/M4V/MKV zu MP4 (H.264) konvertieren
                    elif ext in ['.mov', '.m4v', '.mkv', '.webm']:
                        target_file = os.path.join(IMAGE_FOLDER, name + ".converted.mp4")
                        if not os.path.exists(target_file):
                            print(f"Konvertiere Video: {filename}")
                            # FFmpeg Befehl: Video zu H.264, Audio zu AAC, optimiert für Web
                            cmd = [
                                'ffmpeg', '-i', file_path,
                                '-vcodec', 'libx264', '-acodec', 'aac',
                                '-movflags', 'faststart', # Wichtig für Streaming
                                '-y', target_file
                            ]
                            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        except Exception as e:
            print(f"Fehler im Converter-Thread: {e}")
        
        # Alle 10 Sekunden prüfen
        time.sleep(10)

# Converter im Hintergrund starten
threading.Thread(target=convert_media, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/images')
def get_images():
    media_list = []
    # Wir schauen uns den Ordner an
    files = sorted(os.listdir(IMAGE_FOLDER), key=lambda x: os.path.getmtime(os.path.join(IMAGE_FOLDER, x)), reverse=True)
    
    for filename in files:
        name, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        # Logik: Was zeigen wir an?
        
        # A) Es ist ein fertiges Bild/Video (aber kein konvertiertes Duplikat)
        if ".converted." not in filename:
            
            # Prüfen ob es eine konvertierte Version gibt
            converted_jpg = name + ".converted.jpg"
            converted_mp4 = name + ".converted.mp4"
            
            item = {}
            
            # Fall 1: Original ist Web-Safe (JPG, PNG)
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                item = {"url": filename, "type": "image"}
            
            # Fall 2: Original war HEIC -> Wir nehmen das JPG
            elif os.path.exists(os.path.join(IMAGE_FOLDER, converted_jpg)):
                item = {"url": converted_jpg, "type": "image"}
                
            # Fall 3: Original ist Video (MP4) -> Nehmen wir
            elif ext == '.mp4':
                item = {"url": filename, "type": "video"}

            # Fall 4: Original war MOV etc -> Wir nehmen das MP4
            elif os.path.exists(os.path.join(IMAGE_FOLDER, converted_mp4)):
                item = {"url": converted_mp4, "type": "video"}

            if item:
                media_list.append(item)

    return jsonify(media_list)

@app.route('/api/upload', methods=['POST'])
def upload_image():
    token = request.headers.get('X-Upload-Token')
    if token != UPLOAD_SECRET:
        return jsonify({"error": "Falsches Passwort"}), 403

    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Kein Dateiname"}), 400

    if file:
        ext = os.path.splitext(file.filename)[1].lower()
        unique_filename = str(uuid.uuid4()) + ext
        save_path = os.path.join(IMAGE_FOLDER, unique_filename)
        file.save(save_path)
        return jsonify({"success": True, "filename": unique_filename}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)