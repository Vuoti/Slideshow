import os
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Pfad zu deinem Bilderordner
IMAGE_FOLDER = os.path.join('static', 'images')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/images')
def get_images():
    """
    Scannt den Ordner und gibt eine Liste der Dateinamen zurück.
    Filtert nach typischen Bildformaten.
    """
    images = []
    if os.path.exists(IMAGE_FOLDER):
        for filename in os.listdir(IMAGE_FOLDER):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                images.append(filename)
    
    # Gibt die Liste als JSON zurück
    return jsonify(images)

if __name__ == '__main__':
    # Host='0.0.0.0' macht den Server im lokalen Netzwerk verfügbar
    app.run(host='0.0.0.0', port=6001, debug=True)