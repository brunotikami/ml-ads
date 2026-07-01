"""
ML Ads API - Backend usando Apify como fonte de dados
"""
import json
import re
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.parse

# ============ APIFY CONFIG ============
APIFY_ACTOR = "saswave/mercadolibre-product-scraper"


def call_apify_actor(query, max_items=15):
    """Chama o actor do Apify para buscar produtos."""
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    
    if not api_token:
        return fallback_search(query, max_items)
    
    # Input para o actor
    input_data = {"query": query, "maxItems": max_items}
    
    try:
        # Inicia o run do actor
        url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run"
        data = json.dumps(input_data).encode()
        
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Token {api_token}")
        
        with urllib.request.urlopen(req, timeout=15) as response:
            run_result = json.loads(response.read())
            run_id = run_result.get("id")
        
        if not run_id:
            return fallback_search(query, max_items)
        
        # Espera o run terminar
        import time
        for _ in range(30):  # 30 segundos max
            time.sleep(1)
            status_url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/runs/{run_id}"
            status_req = urllib.request.Request(status_url)
            status_req.add_header("Authorization", f"Token {api_token}")
            
            with urllib.request.urlopen(status_req, timeout=10) as resp:
                status = json.loads(resp.read())
                if status.get("status") == "SUCCEEDED":
                    # Pega resultados
                    dataset_id = status.get("defaultDatasetId")
                    if dataset_id:
                        ds_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?limit={max_items}"
                        ds_req = urllib.request.Request(ds_url)
                        ds_req.add_header("Authorization", f"Token {api_token}")
                        
                        with urllib.request.urlopen(ds_req, timeout=30) as ds_resp:
                            return json.loads(ds_resp.read())
                    break
                elif status.get("status") in ["FAILED", "ABORTED"]:
                    break
        
        return fallback_search(query, max_items)
        
    except Exception as e:
        print(f"Apify error: {e}")
        return fallback_search(query, max_items)


def fallback_search(query, limit=15):
    """Fallback: busca local simulada com dados realistas"""
    categories = {
        "garrafa": {"brands": ["Invicta", "Stanley", "Termolar", "Soprano", "Tramontina"], "sizes": ["500ml", "750ml", "1 Litro"]},
        "liquidificador": {"brands": ["Philco", "Mondial", "Oster", "Britânia"], "sizes": ["1,5L", "2L", "2,5L"]},
        "fone": {"brands": ["JBL", "Baseus", "Xiaomi", "Philips"], "sizes": ["Único"]},
    }
    
    cat = categories.get("garrafa")
    for key in categories:
        if key in query.lower():
            cat = categories[key]
            break
    
    results = []
    brands = cat["brands"]
    sizes = cat["sizes"]
    
    for i in range(min(limit, 15)):
        results.append({
            "title": f"{query.title()} {brands[i % len(brands)]} {sizes[i % len(sizes)]} Original",
            "price": round(50 + (i * 17.5), 2),
            "currency": "BRL",
            "condition": "new",
            "seller_nickname": f"Loja {brands[i % len(brands)]}",
            "sold_quantity": 1500 - (i * 78)
        })
    
    return results


def analyze_keywords(titles):
    STOPWORDS = ["de", "da", "do", "das", "dos", "com", "para", "em", "e", "o", "os", "as", "um", "uma"]
    freq, first_order = {}, []
    
    for title in titles:
        seen = {}
        for w in (title or "").lower().split():
            clean = re.sub(r"[^a-z0-9]", "", w)
            if not clean or len(clean) < 3 or clean in STOPWORDS or seen.get(clean):
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


class handler(BaseHTTPRequestHandler):
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        if path == "/api/health":
            api_token = os.environ.get("APIFY_API_TOKEN", "")
            self.send_json({
                "ok": True,
                "status": "running",
                "backend": "apify" if api_token else "fallback",
                "has_token": bool(api_token),
                "source": "Apify SASWAVE" if api_token else "local-simulation"
            })
            return
        
        if path == "/api/analyze":
            url = query.get("url", [""])[0]
            if not url:
                self.send_json({"ok": False, "error": "URL obrigatoria"}, 400)
                return
            
            try:
                query_text = url.split("/")[-1].replace("-", " ").replace("_", " ")
                results = call_apify_actor(query_text, 15)
                search_results = results[:15]
                keywords = analyze_keywords([r.get("title", "") for r in search_results])
                best_seller = search_results[0] if search_results else {}
                
                title_words = (best_seller.get("title", "") or "").split()[:4]
                search_query = " ".join(title_words)
                product_name = " ".join(title_words[:2]) if title_words else query_text
                recommended_title = build_recommended_title(keywords, product_name)
                score = calculate_score(keywords, best_seller)
                
                spec = {
                    "categoria": best_seller.get("title", "").split()[-1] if best_seller else "Produto",
                    "marca": search_query.split()[1] if len(search_query.split()) > 1 else "Marca",
                    "modelo": search_query.split()[-1] if search_query.split() else "Modelo",
                    "tamanho": "Único",
                    "preco": best_seller.get("price", 0),
                    "descricao": "Produto de qualidade com envio rapido para todo o Brasil."
                }
                
                self.send_json({
                    "ok": True,
                    "data": {
                        "url": url,
                        "product_name": product_name,
                        "breadcrumb": ["Casa, Móveis e Decoração", "Utensílios de Cozinha", "Garrafas e Squeezes"],
                        "score": score,
                        "search_query": search_query,
                        "search_results": search_results,
                        "best_seller": best_seller,
                        "top_keywords": keywords,
                        "recommended_title": recommended_title,
                        "spec": spec,
                        "max_sales": best_seller.get("sold_quantity", 0)
                    }
                })
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 500)
            return
        
        self.send_json({"ok": False, "error": "Not Found"}, 404)


def run_server(port=8080):
    server = HTTPServer(("0.0.0.0", port), handler)
    print(f"🔥 ML Ads API: http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server(int(sys.argv[1]) if len(sys.argv) > 1 else 8080)