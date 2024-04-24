from flask import Flask, render_template, request, redirect, url_for, session, flash, g, send_from_directory, abort
import sqlite3
import requests
import os
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SECRET_KEY, DATABASE

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def get_spotify_token(client_id, client_secret):
    url = "https://accounts.spotify.com/api/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials"}
    try:
        response = requests.post(url, headers=headers, data=data, auth=(client_id, client_secret))
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def get_playlist_tracks(playlist_id, token):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        tracks = []
        for item in response.json()['items']:
            track = item['track']
            track['image_url'] = track['album']['images'][0]['url'] if track['album']['images'] else None
            tracks.append(track)
        return tracks
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return []

@app.route('/')
def home():
    db = get_db()
    sort_by = request.args.get('sort_by', 'top_rated')
    order_clause = 'ORDER BY average_rating DESC'
    if sort_by == 'genre':
        order_clause = 'ORDER BY genre ASC'
    elif sort_by == 'alphabetical':
        order_clause = 'ORDER BY name ASC'
    elif sort_by == 'top_50':
        order_clause = 'ORDER BY average_rating DESC LIMIT 50'

    artist_tracks_query = f"""
    SELECT t.*, COALESCE(AVG(r.rating), 0) AS average_rating
    FROM tracks t
    LEFT JOIN reviews r ON t.id = r.track_id
    GROUP BY t.id
    {order_clause}
    """
    artist_tracks = db.execute(artist_tracks_query).fetchall()
    spotify_tracks = db.execute('SELECT * FROM spotifytracks').fetchall()

    is_logged_in = 'user_id' in session
    username = session.get('username')  # Fetch the username from session

    return render_template('home.html', spotify_tracks=spotify_tracks, artist_tracks=artist_tracks, is_logged_in=is_logged_in, username=username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']  # Store username in session
            flash('You have successfully logged in.')
            return redirect(url_for('home'))  # Redirect to home page after successful login
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        db = get_db()

        # Check if the email or username already exists
        user = db.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        if user:
            flash('Username or email already exists. Please try another one.')
            return redirect(url_for('register'))

        # If not exists, proceed to insert new user
        db.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
        db.commit()
        flash('Registration successful! You can now login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have successfully logged out.')
    return redirect(url_for('home'))

@app.route('/user_page')
def user_page():
    db = get_db()
    user_id = session.get('user_id')

    if user_id is None:
        flash("Please log in to view this page.")
        return redirect(url_for('login'))

    # Fetch the user's reviews from the database
    user_reviews = db.execute('SELECT r.*, t.name as track_name FROM reviews r JOIN tracks t ON r.track_id = t.id WHERE r.user_id = ?', (user_id,)).fetchall()

    return render_template('user_page.html', user_reviews=user_reviews)

@app.route('/review/<track_type>/<track_id>', methods=['GET', 'POST'])
def review(track_type, track_id):
    if 'user_id' not in session:
        flash("Please log in to submit reviews.")
        return redirect(url_for('login'))

    db = get_db()
    track_details = None
    if track_type == 'spotify':
        track_details = db.execute('SELECT * FROM spotifytracks WHERE spotify_id = ?', (track_id,)).fetchone()
    else:  # 'artist' tracks
        track_details = db.execute('SELECT * FROM tracks WHERE id = ?', (track_id,)).fetchone()

    if not track_details:
        flash("Track not found.")
        return redirect(url_for('home'))

    if request.method == 'POST':
        rating = request.form['rating']
        content = request.form['content']
        user_id = session['user_id']
        db.execute('INSERT INTO reviews (track_id, user_id, rating, content, track_type) VALUES (?, ?, ?, ?, ?)',
                   (track_id, user_id, rating, content, track_type))
        db.commit()
        flash('Review submitted successfully!')
        return redirect(url_for('user_page'))

    return render_template('review.html', track=track_details, track_type=track_type)

@app.route('/view_reviews')
def view_reviews():
    track_id = session.get('current_track_id')
    if not track_id:
        flash("No track selected to view reviews.")
        return redirect(url_for('user_page'))

    db = get_db()
    reviews = db.execute('SELECT * FROM reviews WHERE track_id = ?', (track_id,)).fetchall()
    track = db.execute('SELECT * FROM tracks WHERE id = ?', (track_id,)).fetchone()
    if not track:
        flash("Track not found.")
        return redirect(url_for('user_page'))
    return render_template('view_reviews.html', reviews=reviews, track=track)

@app.route('/set_current_track/<track_type>/<track_id>')
def set_current_track(track_type, track_id):
    session['current_track_type'] = track_type
    session['current_track_id'] = track_id
    return redirect(url_for('review', track_type=track_type, track_id=track_id))

@app.route('/create_artist', methods=['GET', 'POST'])
def create_artist():
    if 'user_id' not in session:
        flash("Please log in to create an artist page.")
        return redirect(url_for('login'))

    db = get_db()
    user_id = session['user_id']

    # Check if the artist page already exists
    existing_artist = db.execute('SELECT * FROM artist_pages WHERE user_id = ?', (user_id,)).fetchone()
    if existing_artist:
        return redirect(url_for('artistpage'))  # Redirect to artist page if already exists

    if request.method == 'POST':
        artist_name = request.form['artist_name']
        description = request.form['description']
        genre = request.form['genre']

        db.execute('INSERT INTO artist_pages (artist_name, description, genre, user_id) VALUES (?, ?, ?, ?)',
                   (artist_name, description, genre, user_id))
        db.commit()
        return redirect(url_for('artistpage'))

    return render_template('create_artist.html')

@app.route('/artistpage')
def artistpage():
    if 'user_id' not in session:
        flash('Please log in to access your artist page.')
        return redirect(url_for('login'))

    db = get_db()
    user_id = session['user_id']
    artist_details = db.execute('SELECT * FROM artist_pages WHERE user_id = ?', (user_id,)).fetchone()
    tracks = db.execute('SELECT * FROM tracks WHERE user_id = ?', (user_id,)).fetchall()

    if not artist_details:
        return redirect(url_for('create_artist'))  # Redirect to create artist page if no artist details found

    return render_template('artistpage.html', artist=artist_details, tracks=tracks)

@app.route('/createtrack', methods=['GET', 'POST'])
def createtrack():
    if 'user_id' not in session:
        flash('Please log in to add tracks.')
        return redirect(url_for('login'))
    if request.method == 'POST':
        user_id = session['user_id']
        name = request.form['name']
        artist = request.form['artist']
        album = request.form['album']
        genre = request.form['genre']
        track_file = request.files['track_file']
        if track_file and track_file.filename != '':
            filename = track_file.filename
            track_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            track_file.save(track_path)
            db = get_db()
            db.execute('INSERT INTO tracks (user_id, artist, name, album, genre, file_path) VALUES (?, ?, ?, ?, ?, ?)',
                       (user_id, artist, name, album, genre, filename))
            db.commit()
            flash('New track added successfully.')
        else:
            flash('No file selected for uploading')
        return redirect(url_for('artistpage'))  # Redirect to artist page after adding a track
    # If it's a GET request, render the form to add a new track
    return render_template('createtrack.html')


@app.route('/downloads/<filename>')
def download(filename):
    if 'user_id' not in session:
        flash('Please log in to access downloads.')
        return redirect(url_for('login'))

    # Directly concatenate the upload folder path and filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

@app.route('/delete_track', methods=['POST'])
def delete_track():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))

    track_id = request.form.get('track_id')
    if not track_id:
        flash('Invalid track.')
        return redirect(url_for('artistpage'))

    db = get_db()
    db.execute('DELETE FROM tracks WHERE id = ?', (track_id,))
    db.commit()
    flash('Track deleted successfully.')
    return redirect(url_for('artistpage'))


def insert_spotify_tracks(tracks):
    db = get_db()
    for track in tracks:
        # Checks to see if the track is already in the database to avoid duplicates
        exists = db.execute('SELECT 1 FROM spotifytracks WHERE spotify_id = ?', (track['id'],)).fetchone()
        if not exists:
            db.execute('INSERT INTO spotifytracks (spotify_id, name, artist, album, image_url) VALUES (?, ?, ?, ?, ?)',
                       (track['id'], track['name'], track['artists'][0]['name'], track['album']['name'], track['image_url']))
    db.commit()

@app.route('/edit_track', methods=['POST'])
def edit_track():
    if 'user_id' not in session:
        flash('Please log in to modify tracks.', 'info')
        return redirect(url_for('login'))

    track_id = request.form.get('track_id')
    artist = request.form['artist']
    album = request.form['album']
    name = request.form['name']
    genre = request.form['genre']

    if not track_id:
        flash('Invalid track.', 'error')
        return redirect(url_for('artistpage'))

    db = get_db()
    try:
        db.execute("""
            UPDATE tracks
            SET artist = ?, album = ?, name = ?, genre = ?
            WHERE id = ?
        """, (artist, album, name, genre, track_id))
        db.commit()
        flash('Track updated successfully.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating track: {str(e)}', 'error')

    return redirect(url_for('artistpage'))

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    if file:
        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        db = get_db()
        db.execute('INSERT INTO tracks (name, artist, album, genre, image_url) VALUES (?, ?, ?, ?, ?)',
                   [request.form['name'], request.form['artist'], request.form['album'],
                    request.form['genre'], filename])
        db.commit()
        return redirect(url_for('some_function'))
    return 'File not uploaded', 400

@app.route('/reviews_page')
def reviews_page():
    db = get_db()
    query = """
    SELECT
        users.username,
        COALESCE(tracks.name, spotifytracks.name) AS track_name,
        COALESCE(tracks.artist, spotifytracks.artist) AS artist,
        reviews.rating,
        reviews.content,
        reviews.track_type,
        AVG(reviews.rating) OVER (PARTITION BY reviews.track_id, reviews.track_type) AS average_rating
    FROM reviews
    LEFT JOIN users ON reviews.user_id = users.id
    LEFT JOIN tracks ON reviews.track_id = tracks.id AND reviews.track_type = 'artist'
    LEFT JOIN spotifytracks ON reviews.track_id = spotifytracks.spotify_id AND reviews.track_type = 'spotify'
    """
    reviews = db.execute(query).fetchall()
    return render_template('reviews_page.html', reviews=reviews)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
