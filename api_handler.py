import requests, json, os, sys

class TMDBService:
    def __init__(self):
        self.base_url = "https://api.themoviedb.org/3"
        self.token = self.load_key()
        self.session = requests.Session()
        self.headers = {"accept": "application/json", "Authorization": f"Bearer {self.token}"}
        self.allowed_countries = ['KR', 'JP', 'CN', 'TH', 'TW', 'HK', 'VN', 'PH', 'MY', 'SG', 'ID', 'IN', 'MO']
        
        self.genre_map = {
            "Romance": "k9840", "Action": 10759, "Comedy": 35, "Crime": 80,
            "Drama": 18, "Mystery": 9648, "Sci-Fi & Fantasy": 10765,
            "Wuxia": "k184656", "Xianxia": "k210510"
        }

    def load_key(self):
        user_config = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Vizen', 'config.json')
        if os.path.exists(user_config):
            try:
                with open(user_config, "r") as f:
                    return json.load(f).get("api_key", "")
            except: pass

        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        bundled_config = os.path.join(base_path, "config.json")
        if os.path.exists(bundled_config):
            try:
                with open(bundled_config, "r") as f:
                    return json.load(f).get("api_key", "")
            except: pass
        return ""

    def search_dramas(self, query=None, genre_id=None, country=None, page=1):
        if not self.token: return [], 0
        
        url = f"{self.base_url}/discover/tv"
        params = {
            "language": "en-US", "sort_by": "popularity.desc", "page": page,
            "with_origin_country": country if country else "|".join(self.allowed_countries)
        }

        if isinstance(genre_id, str) and genre_id.startswith('k'):
            params["with_keywords"] = genre_id[1:]
        elif genre_id:
            params["with_genres"] = genre_id

        if query:
            url = f"{self.base_url}/search/tv"
            params = {"query": query, "language": "en-US", "page": page}

        try:
            res = self.session.get(url, params=params, headers=self.headers, timeout=10)
            data = res.json()
            results = data.get('results', [])
            total_pages = data.get('total_pages', 0)
            parsed = [{"id": s['id'], "title": s['name'], 
                     "poster": f"https://image.tmdb.org/t/p/w342{s['poster_path']}" if s['poster_path'] else None, 
                     "year": (s.get('first_air_date') or "????")[:4]} 
                    for s in results if any(c in self.allowed_countries for c in s.get('origin_country', []))]
            return parsed, total_pages
        except: return [], 0

    def get_detailed_info(self, tmdb_id):
        try:
            res = self.session.get(f"{self.base_url}/tv/{tmdb_id}", params={"append_to_response": "credits,watch/providers"}, headers=self.headers, timeout=10)
            data = res.json()
            providers = data.get('watch/providers', {}).get('results', {})
            region = providers.get('US', providers.get('KR', next(iter(providers.values())) if providers else {}))
            streaming = []
            if region and 'flatrate' in region:
                for p in region['flatrate']:
                    streaming.append({
                        "name": p['provider_name'],
                        # Use w92 for better quality icons that still scale down well to 32x32
                        "logo": f"https://image.tmdb.org/t/p/w92{p['logo_path']}" if p.get('logo_path') else None,
                        "url": region.get('link')
                    })
            return {
                "id": data['id'], 
                "title": data['name'], 
                "overview": data.get('overview', 'No description available.'),
                "total_eps": data.get('number_of_episodes', 0), 
                "genres": [g['name'] for g in data.get('genres', [])],
                "origin_country": data.get('origin_country', []), # Add this line
                "cast": [p['name'] for p in data.get('credits', {}).get('cast', [])[:5]],
                "poster": f"https://image.tmdb.org/t/p/w342{data['poster_path']}" if data['poster_path'] else None,
                "year": data.get('first_air_date', '????')[:4], 
                "streaming": streaming
            }
        except: return None