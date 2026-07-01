# ML Ads - Gerador de Anúncios para Mercado Livre

Frontend + Backend para análise e otimização de anúncios do Mercado Livre.

## Links

- **Frontend:** https://brunotikami.github.io/ml-ads/
- **Backend API:** https://ml-ads.vercel.app

## Alternativas de Scraping

### Apify (Atual)

O projeto está configurado para usar o Apify como fonte de dados primária. Para configurar:

1. Crie uma conta em [Apify](https://apify.com)
2. Pegue seu API token em Settings → Tokens
3. Adicione no Vercel:
   ```bash
   vercel env add APIFY_API_TOKEN
   ```

### Alternativas Mais Robustas

Se o Apify não funcionar bem, considere estas alternativas:

| Serviço | Preço | Características |
|---------|--------|------------------|
| **Bright Data** | ~$15/GB | 400M+ IPs residenciais, melhor qualidade |
| **Smartproxy (Decodo)** | ~$2/GB | 115M+ IPs, bom custo-benefício |
| **DataImpulse** | $1/GB | 90M+ IPs, opção mais barato |
| **Spider.cloud** | ~$1.5/GB | 14M+ IPs Brasil |

### Scrapers Prontos

| Actor | Preço | Notas |
|-------|-------|-------|
| **SASWAVE** | $0.0008/result | Mais barato, não precisa proxy |
| **sourabhbgp** | $0.002/result | Multi-país LATAM |
| **viralanalyzer** | $0.012/result | Bom para BR |

## Desenvolvimento Local

```bash
# Clone e setup
cd ml-ads
npm install

# Backend local (Python)
cd api
python main.py 8080

# Frontend
# Abra index.html no navegador ou use um servidor local
npx serve .
```

## Configuração

O frontend detecta automaticamente o ambiente:
- **Localhost:** usa mock local
- **GitHub Pages:** usa API da Vercel
- **API_BASE:** pode ser sobrescrito via `window.API_BASE`

## Licença

MIT
