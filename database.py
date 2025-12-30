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
                year TEXT, rating INTEGER DEFAULT 0, last_updated INTEGER DEFAULT 0
            )
        ''')
        try: cursor.execute('ALTER TABLE dramas ADD COLUMN rating INTEGER DEFAULT 0')
        except: pass
        try: cursor.execute('ALTER TABLE dramas ADD COLUMN last_updated INTEGER DEFAULT 0')
        except: pass
        self.conn.commit()

    def get_library(self, status_filter="all", search_q=""):
        cur = self.conn.cursor()
        query = "SELECT * FROM dramas"
        params = []
        conditions = []
        if status_filter != "all":
            conditions.append("status = ?")
            params.append(status_filter)
        if search_q:
            conditions.append("title LIKE ?")
            params.append(f"%{search_q}%")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY last_updated DESC"
        cur.execute(query, params)
        return [{"id": d[0], "title": d[1], "poster": d[2], "status": d[3], 
                 "current_ep": d[4], "total_eps": d[5], "year": d[6], "rating": d[7]} for d in cur.fetchall()]

    def update_rating(self, tmdb_id, rating):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE dramas SET rating = ? WHERE tmdb_id = ?', (rating, tmdb_id))
        self.conn.commit()

    def add_drama(self, d, status, current_ep=0):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO dramas (tmdb_id, title, poster_url, status, current_ep, total_eps, year, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (d['id'], d['title'], d['poster'], status, current_ep, d.get('total_eps', 0), d['year'], int(time.time())))
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

    def delete_drama(self, tmdb_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM dramas WHERE tmdb_id = ?', (tmdb_id,))
        self.conn.commit()

    def import_data(self, path):
        try:
            with open(path, 'r') as f: data = json.load(f)
            for d in data:
                self.add_drama(d, d['status'], d['current_ep'])
            return True
        except: return False

    def export_data(self, path):
        data = self.get_library()
        with open(path, 'w') as f: json.dump(data, f, indent=4)