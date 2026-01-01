import sqlite3
import json
import time
import os
import sys

class DatabaseHandler:
    def __init__(self):
        # Universal path logic
        if sys.platform == 'win32':
            self.app_folder = os.path.join(os.environ['LOCALAPPDATA'], 'Vizen')
        elif sys.platform == 'darwin': # macOS
            self.app_folder = os.path.expanduser('~/Library/Application Support/Vizen')
        else: # Linux
            self.app_folder = os.path.expanduser('~/.local/share/Vizen')

        if not os.path.exists(self.app_folder):
            os.makedirs(self.app_folder)
            
        db_path = os.path.join(self.app_folder, "dramas.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dramas (
                tmdb_id INTEGER PRIMARY KEY,
                title TEXT, poster_url TEXT, status TEXT,
                current_ep INTEGER DEFAULT 0, total_eps INTEGER DEFAULT 0, 
                year TEXT, rating INTEGER DEFAULT 0, last_updated INTEGER DEFAULT 0,
                genres TEXT DEFAULT "",
                origin_country TEXT DEFAULT ""
            )
        ''')
        # Migrations
        try: cursor.execute('ALTER TABLE dramas ADD COLUMN rating INTEGER DEFAULT 0')
        except: pass
        try: cursor.execute('ALTER TABLE dramas ADD COLUMN last_updated INTEGER DEFAULT 0')
        except: pass
        try: cursor.execute('ALTER TABLE dramas ADD COLUMN genres TEXT DEFAULT ""')
        except: pass
        try: cursor.execute('ALTER TABLE dramas ADD COLUMN origin_country TEXT DEFAULT ""')
        except: pass
        self.conn.commit()

    def get_library(self, status_filter="all", search_q="", genre_filter="All Genres", country_filter="All Regions"):
        cur = self.conn.cursor()
        query = "SELECT * FROM dramas"
        params = []
        conditions = []

        if status_filter and status_filter != "all":
            conditions.append("status = ?")
            params.append(status_filter)
        if search_q:
            conditions.append("title LIKE ?")
            params.append(f"%{search_q}%")
        if genre_filter and genre_filter != "All Genres":
            conditions.append("genres LIKE ?")
            params.append(f"%{genre_filter}%")
        if country_filter and country_filter != "All Regions":
            conditions.append("origin_country LIKE ?")
            params.append(f"%{country_filter}%")
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY last_updated DESC"
        cur.execute(query, params)
        # Note: origin_country is index 10
        return [{"id": d[0], "title": d[1], "poster": d[2], "status": d[3], 
                "current_ep": d[4], "total_eps": d[5], "year": d[6], 
                "rating": d[7], "genres": d[9], "country": d[10]} for d in cur.fetchall()]

    def update_rating(self, tmdb_id, rating):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE dramas SET rating = ? WHERE tmdb_id = ?', (rating, tmdb_id))
        self.conn.commit()

    def add_drama(self, d, status, current_ep=0):
        cursor = self.conn.cursor()
        genres_str = ",".join(d.get('genres', []))
        # Extract country from API data (TMDB returns a list)
        country = d.get('origin_country', [""])[0] if isinstance(d.get('origin_country'), list) else d.get('origin_country', "")
        
        cursor.execute('''
            INSERT OR REPLACE INTO dramas (tmdb_id, title, poster_url, status, current_ep, total_eps, year, last_updated, genres, origin_country)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (d['id'], d['title'], d['poster'], status, current_ep, d.get('total_eps', 0), d['year'], int(time.time()), genres_str, country))
        self.conn.commit()

    def update_episode(self, tmdb_id, new_ep):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE dramas SET current_ep = ?, last_updated = ? WHERE tmdb_id = ?', 
                       (new_ep, int(time.time()), tmdb_id))
        self.conn.commit()

    def update_status(self, tmdb_id, status, current_ep):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE dramas SET status = ?, current_ep = ?, last_updated = ? WHERE tmdb_id = ?', 
                       (status, current_ep, int(time.time()), tmdb_id))
        self.conn.commit()

    def get_incomplete_dramas(self):
        cursor = self.conn.cursor()
        # Find dramas where genres are empty OR country is empty
        cursor.execute("SELECT tmdb_id FROM dramas WHERE genres = '' OR origin_country = '' OR origin_country IS NULL")
        return [row[0] for row in cursor.fetchall()]

    def delete_drama(self, tmdb_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM dramas WHERE tmdb_id = ?', (tmdb_id,))
        self.conn.commit()

    def import_data(self, path):
        try:
            with open(path, 'r') as f: data = json.load(f)
            for d in data:
                self.add_drama(d, d['status'], d.get('current_ep', 0))
            return True
        except: return False

    def export_data(self, path):
        data = self.get_library()
        with open(path, 'w') as f: json.dump(data, f, indent=4)