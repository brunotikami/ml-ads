"""
API para scraping do Mercado Livre
Usa a API não-oficial do ML via servidor proxy
"""
import os
import json
import re
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.parse

# URL da API do ML (não-oficial)
ML_API_BASE = "https://api.mercadolibre.com"

class handler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        path = self.path.split('?')[0]
        
        if path == '/api/health':
            self.send_json({'ok': True, 'status': 'running'})
        
        elif path == '/api/scrape':
            # Parse URL parameter
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            url = query.get('url', [''])[0]
            
            if not url:
                self.send_json({'ok': False, 'error': 'URL é obrigatória. Use ?url=...'}, 400)
                return
            
            # Extrai ID do produto da URL
            product_id = self.extract_product_id(url)
            if not product_id:
                self.send_json({'ok': False, 'error': 'URL inválida. Use URL de produto do ML'}, 400)
                return
            
            # Busca dados da API do ML
            data = self.scrape_product(product_id)
            self.send_json({'ok': True, 'data': data})
        
        elif path == '/api/search':
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            q = query.get('q', [''])[0]
            
            if not q:
                self.send_json({'ok': False, 'error': 'Query é obrigatória. Use ?q=...'}, 400)
                return
            
            results = self.search_products(q)
            self.send_json({'ok': True, 'results': results})
        
        else:
            self.send_json({'ok': False, 'error': 'Endpoint não encontrado'}, 404)
    
    def extract_product_id(self, url):
        """Extrai ID do produto de uma URL do ML"""
        # Padrões: /p/MLB123456789 ou /MLB123456789
        patterns = [
            r'/p/([A-Z0-9]+)',
            r'/([A-Z]{2,3}[0-9]{8,10})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def scrape_product(self, product_id):
        """Busca dados do produto via API do ML"""
        try:
            # API de item
            item_url = f"{ML_API_BASE}/items/{product_id}"
            with urllib.request.urlopen(item_url, timeout=10) as response:
                item = json.loads(response.read())
            
            # API de descrição
            desc_url = f"{ML_API_BASE}/items/{product_id}/description"
            try:
                with urllib.request.urlopen(desc_url, timeout=10) as response:
                    desc_data = json.loads(response.read())
                    description = desc_data.get('plain_text', '')
            except:
                description = ''
            
            return {
                'id': item.get('id'),
                'title': item.get('title'),
                'price': item.get('price'),
                'currency': item.get('currency_id'),
                'category': item.get('category_id'),
                'category_name': item.get('category_path', []),
                'condition': item.get('condition'),
                'status': item.get('status'),
                'pictures': [p.get('url') for p in item.get('pictures', [])],
                'seller': {
                    'id': item.get('seller_id'),
                    'nickname': item.get('seller', {}).get('nickname'),
                },
                'available_quantity': item.get('available_quantity'),
                'sold_quantity': item.get('sold_quantity'),
                'description': description[:500],
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def search_products(self, query):
        """Busca produtos via API do ML"""
        try:
            search_url = f"{ML_API_BASE}/sites/MLB/search?q={urllib.parse.quote(query)}&limit=10"
            with urllib.request.urlopen(search_url, timeout=10) as response:
                data = json.loads(response.read())
            
            results = []
            for item in data.get('results', [])[:10]:
                results.append({
                    'id': item.get('id'),
                    'title': item.get('title'),
                    'price': item.get('price'),
                    'currency': item.get('currency_id'),
                    'thumbnail': item.get('thumbnail'),
                    'condition': item.get('condition'),
                    'seller': item.get('seller', {}).get('nickname'),
                    'sold_quantity': item.get('sold_quantity'),
                })
            
            return results
            
        except Exception as e:
            return [{'error': str(e)}]
