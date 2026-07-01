"""
ML Ads API - Backend com scraping real da API do Mercado Livre
Tenta urllib primeiro, fallback para subprocess em caso de erro de sandbox
"""
import json
import re
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.parse
import subprocess

ML_API_BASE = "https://api.mercadolibre.com"


def fetch_url(url, timeout=15):
    """
    Tenta urllib primeiro, se falhar usa subprocess/curl.
    Isso contorna limitacoes de sandbox em alguns ambientes.
    """
    # Tenta urllib primeiro
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode()
    except Exception as e:
        err_msg = str(e)
        # Se for erro de rede/sandbox, tenta curl via subprocess
        if "Network is unreachable" in err_msg or "timed out" in err_msg.lower() or "Forbidden" in err_msg:
            return fetch_url_subprocess(url, timeout)
        raise


def fetch_url_subprocess(url, timeout=15):
    """Fallback: executa curl via subprocess"""
    cmd = ["curl", "-s", "-m", str(timeout), url]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        if result.returncode != 0:
            raise Exception(f"curl failed: {result.stderr}")
        return result.stdout
    except FileNotFoundError:
        raise Exception("curl not available")
    except subprocess.TimeoutExpired:
        raise Exception("Timeout")


def extract_product_id(url):
    """Extrai ID do produto de uma URL do ML"""
    patterns = [
        r'/p/([A-Z0-9]+)',
        r'/item/([A-Z0-9]+)',
        r'/([A-Z]{2,3}[0-9]{8,10})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def scrape_product_api(product_id):
    """Busca dados do produto via API do ML"""
    # Busca item
    item_url = f"{ML_API_BASE}/items/{product_id}"
    data = fetch_url(item_url)
    item = json.loads(data)
    
    if "error" in item:
        return item
    
    # Busca descricao
    desc_url = f"{ML_API_BASE}/items/{product_id}/description"
    try:
        desc_data = fetch_url(desc_url)
        desc = json.loads(desc_data)
        description = desc.get("plain_text", "")[:500]
    except:
        description = ""
    
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "price": item.get("price"),
        "currency": item.get("currency_id"),
        "category": item.get("category_id"),
        "condition": item.get("condition"),
        "status": item.get("status"),
        "pictures": [p.get("url") for p in item.get("pictures", [])[:5]],
        "seller_id": item.get("seller_id"),
        "available_quantity": item.get("available_quantity"),
        "sold_quantity": item.get("sold_quantity"),
        "description": description,
    }


def search_products_api(query, limit=15):
    """Busca produtos via API do ML"""
    search_url = f"{ML_API_BASE}/sites/MLB/search?q={urllib.parse.quote(query)}&limit={limit}"
    data = fetch_url(search_url)
    results_data = json.loads(data)
    
    results = []
    for item in results_data.get("results", [])[:limit]:
        results.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "price": item.get("price"),
            "currency": item.get("currency_id"),
            "thumbnail": item.get("thumbnail"),
            "condition": item.get("condition"),
            "seller_nickname": item.get("seller", {}).get("nickname"),
            "sold_quantity": item.get("sold_quantity"),
        })
    
    return results


def get_category_path(category_id):
    """Busca caminho da categoria"""
    cat_url = f"{ML_API_BASE}/categories/{category_id}"
    try:
        data = fetch_url(cat_url)
        cat = json.loads(data)
        path = cat.get("path_from_root", [])
        return [p.get("name") for p in path]
    except:
        return []


class handler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        # Health check
        if path == "/api/health":
            self.send_json({"ok": True, "status": "running", "backend": "python-urllib"})
            return
        
        # Scrape produto
        if path == "/api/scrape":
            url = query.get("url", [""])[0]
            if not url:
                self.send_json({"ok": False, "error": "URL e obrigatoria"}, 400)
                return
            
            product_id = extract_product_id(url)
            if not product_id:
                self.send_json({"ok": False, "error": "URL invalida"}, 400)
                return
            
            data = scrape_product_api(product_id)
            if "error" in data:
                self.send_json({"ok": False, "error": data["error"]}, 500)
            else:
                self.send_json({"ok": True, "data": data})
            return
        
        # Busca produtos
        if path == "/api/search":
            q = query.get("q", [""])[0]
            if not q:
                self.send_json({"ok": False, "error": "Query obrigatoria"}, 400)
                return
            
            limit = int(query.get("limit", ["15"])[0])
            results = search_products_api(q, limit)
            self.send_json({"ok": True, "results": results, "total": len(results)})
            return
        
        # Analise completa
        if path == "/api/analyze":
            url = query.get("url", [""])[0]
            if not url:
                self.send_json({"ok": False, "error": "URL obrigatoria"}, 400)
                return
            
            try:
                # 1) Scrape do produto original
                product_id = extract_product_id(url)
                if not product_id:
                    raise Exception("ID do produto invalido")
                
                product = scrape_product_api(product_id)
                if "error" in product:
                    raise Exception(product["error"])
                
                # 2) Busca termos (4 primeiras palavras do titulo)
                title_words = product.get("title", "").split()[:4]
                search_query = " ".join(title_words)
                if not search_query:
                    search_query = url.split("/")[-1].replace("-", " ")
                
                # 3) Busca resultados
                search_results = search_products_api(search_query, 15)
                
                # 4) Analisa palavras-chave
                all_titles = [r.get("title", "") for r in search_results]
                keywords = analyze_keywords(all_titles)
                
                # 5) Best seller
                best_seller = search_results[0] if search_results else {}
                
                # 6) Titulo recomendado
                product_name = " ".join(title_words[:2])
                recommended_title = build_recommended_title(keywords, product_name)
                
                # 7) Score
                score = calculate_score(keywords, best_seller)
                
                # 8) Descricao
                description = product.get("description") or f"Produto de qualidade com envio rapido."
                
                # 9) Ficha tecnica
                spec = {
                    "categoria": best_seller.get("title", "").split()[-1] if best_seller else "Produto",
                    "marca": search_query.split()[1] if len(search_query.split()) > 1 else "Marca",
                    "modelo": search_query.split()[-1] if search_query.split() else "Modelo",
                    "tamanho": "Unico",
                    "preco": best_seller.get("price") or product.get("price") or 0,
                    "descricao": description
                }
                
                self.send_json({
                    "ok": True,
                    "data": {
                        "url": url,
                        "product_name": product.get("title"),
                        "breadcrumb": get_category_path(product.get("category")),
                        "score": score,
                        "search_query": search_query,
                        "search_results": search_results,
                        "best_seller": best_seller,
                        "top_keywords": keywords,
                        "recommended_title": recommended_title,
                        "spec": spec,
                        "max_sales": best_seller.get("sold_quantity", 0) if best_seller else 0
                    }
                })
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 500)
            return
        
        # Leads (in-memory store)
        if path == "/api/leads":
            if self.command == "GET":
                self.send_json({"ok": True, "leads": LEADS, "total": len(LEADS)})
                return
            return
        
        self.send_json({"ok": False, "error": "Not Found"}, 404)


# ============ Analise de Palavras-Chave ============
STOPWORDS = ["de", "da", "do", "das", "dos", "com", "para", "em", "e", "o", "os", "as", "um", "uma"]


def analyze_keywords(titles):
    """Extrai palavras-chave mais frequentes"""
    freq = {}
    first_order = []
    
    for title in titles:
        seen = {}
        words = (title or "").lower().split()
        for w in words:
            clean = re.sub(r"[^a-z0-9]", "", w)
            if not clean or len(clean) < 3 or clean in STOPWORDS:
                continue
            if seen.get(clean):
                continue
            seen[clean] = True
            if clean not in freq:
                freq[clean] = 0
                first_order.append(clean)
            freq[clean] += 1
    
    ranked = first_order[:]
    ranked.sort(key=lambda w: freq[w], reverse=True)
    
    return [{"word": w, "count": freq[w]} for w in ranked[:9]]


def build_recommended_title(keywords, product_name, max_len=60):
    """Constroi titulo recomendado"""
    words = [product_name] + [k["word"] for k in keywords[:4]]
    title = " ".join(words)
    if len(title) <= max_len:
        return title
    
    parts = title.split()
    result = parts[0]
    for i in range(1, len(parts)):
        if len(result) + len(parts[i]) + 1 > max_len:
            break
        result += " " + parts[i]
    return result


def calculate_score(keywords, best_seller):
    """Calcula score de performance"""
    score = 75
    if len(keywords) >= 5:
        score += 10
    if best_seller:
        sales = best_seller.get("sold_quantity", 0)
        if sales > 300:
            score += 8
        elif sales > 100:
            score += 4
    return min(95, score)


# ============ In-Memory Store ============
LEADS = []


def run_server(port=8080):
    server = HTTPServer(("0.0.0.0", port), handler)
    print(f"🔥 ML Ads API rodando em http://localhost:{port}")
    print(f"   Health:   GET  http://localhost:{port}/api/health")
    print(f"   Analyze: GET  http://localhost:{port}/api/analyze?url=...")
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)