from scholarly import scholarly, ProxyGenerator
import jsonpickle
import json
from datetime import datetime
import os

pg = ProxyGenerator()
pg.ScraperAPI(os.environ['SCRAPER_API_KEY'])

# Use ScraperAPI as both the primary and the secondary (fallback) proxy.
# Passing an explicit secondary stops scholarly from auto-creating a
# FreeProxies() fallback at setup time, which crashes on recent `free-proxy`
# releases (get_proxy_list() now requires a `repeat` arg that scholarly 1.7.11
# calls without) and is what makes this job fail most runs.
pg_fallback = ProxyGenerator()
pg_fallback.ScraperAPI(os.environ['SCRAPER_API_KEY'])
scholarly.use_proxy(pg, pg_fallback)

author: dict = scholarly.search_author_id(os.environ['GOOGLE_SCHOLAR_ID'])
scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
name = author['name']
author['updated'] = str(datetime.now())
author['publications'] = {v['author_pub_id']:v for v in author['publications']}
print(json.dumps(author, indent=2))
os.makedirs('results', exist_ok=True)
with open(f'results/gs_data.json', 'w') as outfile:
    json.dump(author, outfile, ensure_ascii=False)

shieldio_data = {
  "schemaVersion": 1,
  "label": "citations",
  "message": f"{author['citedby']}",
}
with open(f'results/gs_data_shieldsio.json', 'w') as outfile:
    json.dump(shieldio_data, outfile, ensure_ascii=False)
