# API Serverless para scraping do Mercado Livre

## Endpoints

### GET /api/scrape
Faz scraping de um anúncio do ML e retorna dados estruturados.

**Parâmetros:**
- `url` (query string) - URL do anúncio do ML

**Response:**
```json
{
  "ok": true,
  "data": {
    "title": "Garrafa Térmica Inox 1L",
    "price": 89.90,
    "category": "Casa e Decoração > Utensílios de Cozinha",
    "breadcrumbs": ["Casa", "Utensílios de Cozinha", "Garrafas"],
    "images": ["https://http..."],
    "seller": {
      "nickname": "lojaoficial",
      "reputation": "green_plus"
    },
    "sales": 1250
  }
}
```

### GET /api/search
Busca produtos no ML e retorna os top resultados.

**Parâmetros:**
- `q` (query string) - termo de busca

**Response:**
```json
{
  "ok": true,
  "results": [...]
}
```
