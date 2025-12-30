import requests, json, os, sys

class TMDBService:
    def __init__(self):
        self.base_url = "https://api.themoviedb.org/3"
        self.token = self.load_key()
        self.session = requests.Session()
        self.headers = {"accept": "application/json", "Authorization": f"Bearer {self.token}"}
        self.allowed_countries = ['KR', 'JP', 'CN', 'TH', 'TW', 'HK', 'VN', 'PH', 'MY', 'SG', 'ID', 'IN', 'MO']

    def load_key(self):
        user_config = os.path.join(os.environ['LOCALAPPDATA'], 'Vizen', 'config.json')
        if os.path.exists(user_config):
            with open(user_config, "r") as f:
                return json.load(f).get("api_key", "")
        base_path = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        bundled_config = os.path.join(base_path, "config.json")
        return json.load(open(bundled_config)).get("api_key", "") if os.path.exists(bundled_config) else ""

    def search_dramas(self, query):
        if not self.token: return []
        try:
            res = self.session.get(f"{self.base_url}/search/tv", params={"query": query, "language": "en-US"}, headers=self.headers, timeout=10)
            results = res.json().get('results', [])
            return [{"id": s['id'], "title": s['name'], "poster": f"https://image.tmdb.org/t/p/w342{s['poster_path']}" if s['poster_path'] else None, "year": (s.get('first_air_date') or "????")[:4]} 
                    for s in results if any(c in self.allowed_countries for c in s.get('origin_country', []))]
        except: return []

    def get_detailed_info(self, tmdb_id):
        try:
            res = self.session.get(f"{self.base_url}/tv/{tmdb_id}", params={"append_to_response": "credits", "language": "en-US"}, headers=self.headers, timeout=10)
            data = res.json()
            return {"id": data['id'], "title": data['name'], "overview": data.get('overview', 'No description available.'), "total_eps": data.get('number_of_episodes', 0),
                    "genres": [g['name'] for g in data.get('genres', [])], "cast": [p['name'] for p in data.get('credits', {}).get('cast', [])[:5]],
                    "poster": f"https://image.tmdb.org/t/p/w342{data['poster_path']}" if data['poster_path'] else None, "year": data.get('first_air_date', '????')[:4]}
        except: return None