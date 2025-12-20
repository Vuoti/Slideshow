import os
import shutil
import time
import threading
import uuid
import subprocess
import logging
from flask import Flask, render_template, jsonify, request
from PIL import Image
from pillow_heif import register_heif_opener

# Logging aktivieren, damit wir Fehler in der Konsole sehen
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

register_heif_opener()

app = Flask(__name__)

IMAGE_FOLDER = os.path.join('static', 'images')
UPLOAD_SECRET = "oma-ist-die-beste"

os.makedirs(IMAGE_FOLDER, exist_ok=True)

def convert_media():
    while True:
        try:
            if os.path.exists(IMAGE_FOLDER):
                for filename in os.listdir(IMAGE_FOLDER):
                    file_path = os.path.join(IMAGE_FOLDER, filename)
                    name, ext = os.path.splitext(filename)
                    ext = ext.lower()

                    # WICHTIG: Prüfen, ob Datei vollständig hochgeladen ist.
                    # Wir warten, bis die Datei seit 5 Sekunden nicht mehr angefasst wurde.
                    try:
                        if (time.time() - os.path.getmtime(file_path)) < 5:
                            continue # Überspringen, Datei ist zu neu (evtl. noch Upload)
                    except FileNotFoundError:
                        continue

                    # --- HEIC zu JPG ---
                    if ext == '.heic':
                        target_file = os.path.join(IMAGE_FOLDER, name + ".converted.jpg")
                        if not os.path.exists(target_file):
                            logger.info(f"Starte Konvertierung: {filename}")
                            try:
                                img = Image.open(file_path)
                                img.save(target_file, "JPEG", quality=90)
                                logger.info(f"Fertig: {target_file}")
                            except Exception as e:
                                logger.error(f"Fehler bei {filename}: {e}")

                    # --- MOV/M4V/MKV zu MP4 ---
                    elif ext in ['.mov', '.m4v', '.mkv', '.webm']:
                        target_file = os.path.join(IMAGE_FOLDER, name + ".converted.mp4")
                        if not os.path.exists(target_file):
                            logger.info(f"Starte Video-Konvertierung: {filename}")
                            
                            ffmpeg_path = '/usr/bin/ffmpeg'
                            found_path = shutil.which('ffmpeg')
                            if found_path:
                                ffmpeg_path = found_path

                            # Befehl angepasst:
                            # -pix_fmt yuv420p: Zwingend nötig für Apple HDR Videos im Web
                            # -vf scale...: Skaliert riesige 4K Videos auf FullHD (spart Platz/Last)
                            cmd = [
                                '/usr/bin/ffmpeg', '-i', file_path,
                                '-vcodec', 'libx264',
                                '-pix_fmt', 'yuv420p', 
                                '-vf', 'scale=1920:-2', 
                                '-acodec', 'aac',
                                '-movflags', 'faststart',
                                '-y', target_file
                            ]
                            
                            # Wir lassen uns jetzt Errors anzeigen
                            result = subprocess.run(cmd, capture_output=True, text=True)
                            
                            if result.returncode == 0:
                                logger.info(f"Video fertig: {target_file}")
                            else:
                                logger.error(f"FFmpeg Fehler bei {filename}:\n{result.stderr}")

        except Exception as e:
            logger.error(f"Globaler Fehler im Converter-Thread: {e}")
        
        time.sleep(10)

threading.Thread(target=convert_media, daemon=True).start()

# --- Der Rest bleibt gleich ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/images')
def get_images():
    media_list = []
    files = sorted(os.listdir(IMAGE_FOLDER), key=lambda x: os.path.getmtime(os.path.join(IMAGE_FOLDER, x)), reverse=True)
    
    for filename in files:
        name, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        if ".converted." not in filename:
            converted_jpg = name + ".converted.jpg"
            converted_mp4 = name + ".converted.mp4"
            
            item = {}
            
            # Priorität: Konvertierte Dateien nutzen
            if os.path.exists(os.path.join(IMAGE_FOLDER, converted_jpg)):
                 item = {"url": converted_jpg, "type": "image"}
            elif os.path.exists(os.path.join(IMAGE_FOLDER, converted_mp4)):
                 item = {"url": converted_mp4, "type": "video"}
            # Fallbacks
            elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
                item = {"url": filename, "type": "image"}
            elif ext == '.mp4':
                item = {"url": filename, "type": "video"}

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
        logger.info(f"Neuer Upload empfangen: {unique_filename}")
        return jsonify({"success": True, "filename": unique_filename}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6001)