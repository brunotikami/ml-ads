/**
 * API para scraping do Mercado Livre e captura de leads
 * Versão com apenas módulos nativos do Node.js (sem dependências externas)
 * 
 * Endpoints:
 *   GET  /api/health          - Health check
 *   POST /api/leads          - Salvar email do lead
 *   GET  /api/leads          - Listar leads (admin)
 *   GET  /api/scrape         - Scraping de produto por URL (simulado)
 *   GET  /api/search        - Busca produtos no ML (simulado)
 *   GET  /api/analyze       - Análise completa: produto → busca → análise
 */
const http = require('http');
const url = require('url');
const path = require('path');

const PORT = process.env.PORT || 8080;

// ============ In-Memory Store ============
const leads = [];
const products = new Map();

// ============ Utils ============
function extractProductId(urlStr) {
  const patterns = [/\/p\/([A-Z]{2,3}\d+)/i, /\/item\/([A-Z]{2,3}\d+)/i, /\/([A-Z]{2,3}\d{8,})/i];
  for (const pattern of patterns) {
    const match = urlStr.match(pattern);
    if (match) return match[1];
  }
  return 'MLB' + Math.floor(Math.random() * 100000000);
}

function extractSearchQuery(urlStr) {
  try {
    const urlObj = new URL(urlStr.startsWith('http') ? urlStr : `https://${urlStr}`);
    if (urlObj.pathname.includes('/busca')) {
      return urlObj.pathname.split('/busca').pop().replace(/-/g, ' ');
    }
    return urlObj.searchParams.get('q') || urlObj.pathname.split('/').pop().replace(/-/g, ' ');
  } catch {
    return urlStr.replace(/https?:\/\//, '').replace(/-/g, ' ');
  }
}

// ============ Simulated Scraping Functions ============
function scrapeProduct(urlStr) {
  const productId = extractProductId(urlStr);
  const query = extractSearchQuery(urlStr);
  
  return {
    url: urlStr,
    product_id: productId,
    title: query.split(' ').slice(0, 3).join(' ') + ' - Original',
    price: Math.round((50 + Math.random() * 200) * 100) / 100,
    category: ['Casa, Móveis e Decoração', 'Utensílios de Cozinha', query.split(' ')[0] || 'Produto'],
    images: [`https://http.cat/200?text=${encodeURIComponent(query)}`],
    seller: 'Loja Oficial',
    reputation: 'green_plus',
    sold_quantity: Math.floor(Math.random() * 500) + 100
  };
}

function searchProducts(query, limit = 15) {
  const brands = ['Philco', 'Mondial', 'Oster', 'Britânia', 'Philips'];
  const suffixes = ['Original', 'Premium', 'Profissional', 'Compacto', 'Resistente'];
  
  return Array.from({ length: limit }, (_, i) => ({
    pos: i + 1,
    url: `https://www.mercadolivre.com.br/${query.replace(/ /g, '-')}-${brands[i % brands.length]}/p/MLB${1000000 + i}`,
    title: `${query} ${brands[i % brands.length]} ${suffixes[i % suffixes.length]}`,
    price: Math.round((35 + Math.random() * 280) * 100) / 100,
    thumbnail: null,
    sales: Math.max(50, 1450 - i * 78)
  }));
}

function analyzeResults(results) {
  const wordFreq = {};
  const firstOrder = [];
  const stopwords = ['de', 'da', 'do', 'das', 'dos', 'com', 'para', 'em', 'e', 'o', 'os', 'as', 'um', 'uma'];
  
  results.forEach(r => {
    const seen = {};
    const words = (r.title || '').toLowerCase().split(/\s+/);
    words.forEach(w => {
      const clean = w.replace(/[^a-záàâãéèêíïóôõöúçñ]/g, '');
      if (!clean || clean.length < 3 || stopwords.includes(clean)) return;
      if (seen[clean]) return;
      seen[clean] = true;
      if (!wordFreq[clean]) {
        wordFreq[clean] = 0;
        firstOrder.push(clean);
      }
      wordFreq[clean]++;
    });
  });
  
  const ranked = firstOrder.slice().sort((a, b) => {
    if (wordFreq[b] !== wordFreq[a]) return wordFreq[b] - wordFreq[a];
    return firstOrder.indexOf(a) - firstOrder.indexOf(b);
  });
  
  return ranked.slice(0, 9).map(w => ({ word: w, count: wordFreq[w] }));
}

function buildRecommendedTitle(keywords, productName, maxLen = 60) {
  const words = [productName, ...keywords.slice(0, 4)].join(' ');
  if (words.length <= maxLen) return words;
  
  const parts = words.split(' ');
  let result = parts[0];
  for (let i = 1; i < parts.length; i++) {
    if (result.length + parts[i].length + 1 > maxLen) break;
    result += ' ' + parts[i];
  }
  return result;
}

function calculateScore(keywords, bestSeller) {
  let score = 75;
  if (keywords.length >= 5) score += 10;
  if (bestSeller && bestSeller.sales > 300) score += 8;
  if (bestSeller && bestSeller.sales > 100) score += 4;
  return Math.min(95, score);
}

// ============ HTTP Server ============
const server = http.createServer(async (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const parsedUrl = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = parsedUrl.pathname;
  const query = Object.fromEntries(parsedUrl.searchParams);

  // ============ Routes ============
  
  // Health check
  if (pathname === '/api/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, status: 'running', timestamp: new Date().toISOString() }));
    return;
  }

  // Capturar lead (POST)
  if (pathname === '/api/leads' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const { email, url: leadUrl, product_title } = JSON.parse(body);
        
        if (!email) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: 'Email é obrigatório' }));
          return;
        }
        
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: 'Email inválido' }));
          return;
        }
        
        const lead = {
          id: 'lead-' + Date.now(),
          email,
          url: leadUrl || null,
          product_title: product_title || null,
          created_at: new Date().toISOString()
        };
        
        leads.push(lead);
        console.log('Lead captured:', lead.email);
        
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, lead }));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  // Listar leads (GET)
  if (pathname === '/api/leads' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, leads, total: leads.length }));
    return;
  }

  // Scraping de produto (simulado)
  if (pathname === '/api/scrape' && req.method === 'GET') {
    if (!query.url) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: 'URL é obrigatória. Use ?url=...' }));
      return;
    }
    
    const data = scrapeProduct(query.url);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, data }));
    return;
  }

  // Busca produtos (simulada)
  if (pathname === '/api/search' && req.method === 'GET') {
    if (!query.q) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: 'Query é obrigatória. Use ?q=...' }));
      return;
    }
    
    const results = searchProducts(query.q, parseInt(query.limit) || 15);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, results, total: results.length }));
    return;
  }

  // Análise completa (endpoint principal)
  if (pathname === '/api/analyze' && req.method === 'GET') {
    if (!query.url) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: 'URL é obrigatória. Use ?url=...' }));
      return;
    }
    
    try {
      // 1) Scrape do produto original
      const product = scrapeProduct(query.url);
      
      // 2) Busca termos
      const searchQuery = (product.title || extractSearchQuery(query.url))
        .split(' ').slice(0, 4).join(' ');
      
      // 3) Busca os 15 primeiros resultados
      const searchResults = searchProducts(searchQuery, 15);
      
      // 4) Analisa palavras-chave
      const keywords = analyzeResults(searchResults);
      
      // 5) Best seller
      const bestSeller = searchResults[0] || {};
      
      // 6) Título recomendado
      const productName = (product.title || searchQuery).split(' ').slice(0, 2).join(' ');
      const recommendedTitle = buildRecommendedTitle(keywords, productName);
      
      // 7) Score
      const score = calculateScore(keywords, bestSeller);
      
      // 8) Descrição
      const description = `Conheça este ${productName.toLowerCase()}, com construção reforçada e acabamento premium. ` +
        `Indicado para uso diário, com garantia do vendedor e envio rápido para todo o Brasil.`;
      
      // 9) Ficha técnica
      const spec = {
        category: product.category[product.category.length - 1],
        brand: bestSeller.title?.split(' ')[1] || 'Marca',
        modelo: searchQuery.split(' ').slice(-1)[0] || 'Modelo',
        tamanho: bestSeller.title?.match(/\d+[mlL]?\b/i)?.[0] || 'Único',
        preco: bestSeller.price || product.price,
        descricao: description
      };
      
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        ok: true,
        data: {
          url: query.url,
          product_name: productName,
          breadcrumb: product.category,
          score,
          search_query: searchQuery,
          search_results: searchResults,
          best_seller: bestSeller,
          top_keywords: keywords,
          recommended_title: recommendedTitle,
          spec,
          max_sales: bestSeller.sales || 0
        }
      }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: err.message }));
    }
    return;
  }

  // 404
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ ok: false, error: 'Not Found' }));
});

// ============ Start Server ============
server.listen(PORT, '0.0.0.0', () => {
  console.log(`🔥 ML Ads API rodando em http://localhost:${PORT}`);
  console.log(`   Health:    GET  http://localhost:${PORT}/api/health`);
  console.log(`   Leads:   POST http://localhost:${PORT}/api/leads`);
  console.log(`   Analyze: GET  http://localhost:${PORT}/api/analyze?url=...`);
});

module.exports = server;