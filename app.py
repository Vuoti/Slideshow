import os
import uuid
from flask import Flask, render_template, jsonify, request, abort

app = Flask(__name__)

# Konfiguration
IMAGE_FOLDER = os.path.join('static', 'images')
UPLOAD_SECRET = "oma-ist-die-beste" 

# Sicherstellen, dass der Ordner existiert
os.makedirs(IMAGE_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/images')
def get_images():
    images = []
    # Sortieren nach Datum (neueste zuerst), damit neue Bilder gleich kommen
    files = sorted(os.listdir(IMAGE_FOLDER), key=lambda x: os.path.getmtime(os.path.join(IMAGE_FOLDER, x)), reverse=True)
    
    for filename in files:
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            images.append(filename)
    return jsonify(images)

@app.route('/api/upload', methods=['POST'])
def upload_image():
    # 1. Sicherheitsschlüssel prüfen
    token = request.headers.get('X-Upload-Token')
    if token != UPLOAD_SECRET:
        return jsonify({"error": "Falsches Passwort"}), 403

    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "Kein Dateiname"}), 400

    if file:
        # Wir geben dem Bild einen eindeutigen Namen, um Überschreiben zu verhindern
        # und Probleme mit Sonderzeichen zu vermeiden
        ext = os.path.splitext(file.filename)[1].lower()
        unique_filename = str(uuid.uuid4()) + ext
        save_path = os.path.join(IMAGE_FOLDER, unique_filename)
        
        file.save(save_path)
        return jsonify({"success": True, "filename": unique_filename}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6001)