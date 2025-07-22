
from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urldefrag
from concurrent.futures import ThreadPoolExecutor
import time

app = Flask(__name__)

EXCLUDED_DOMAINS = [
    'g.co', 'facebook.com', 'instagram.com', 'x.com', 'twitter.com',
    'pinterest.com', 'shopify.com', 'edpb.europa.eu'
]

def normalize_domain(domain):
    return domain.lower().replace("www.", "")

def crawl_site(start_url):
    visited = set()
    to_visit = [start_url]
    outbound_links = set()
    broken_links = set()
    pages_scanned = 0
    domain = normalize_domain(urlparse(start_url).netloc)

    with ThreadPoolExecutor(max_workers=10) as executor:
        while to_visit:
            url = to_visit.pop(0)
            if url in visited:
                continue
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 404:
                    broken_links.add(url)
                    continue
                soup = BeautifulSoup(response.text, "html.parser")
                visited.add(url)

                for a in soup.find_all("a", href=True):
                    href = a['href'].strip()
                    if href.startswith(("mailto:", "javascript:", "tel:", "#")):
                        continue
                    raw_url = urldefrag(urljoin(url, href))[0]
                    parsed = urlparse(raw_url)
                    netloc = normalize_domain(parsed.netloc)
                    normalized_url = parsed._replace(netloc=netloc).geturl()

                    if netloc == "" or domain in netloc:
                        if normalized_url not in visited and normalized_url not in to_visit:
                            to_visit.append(normalized_url)
                    else:
                        if any(skip in netloc for skip in EXCLUDED_DOMAINS):
                            continue
                        if normalized_url not in outbound_links:
                            outbound_links.add(normalized_url)
                            try:
                                ext_resp = requests.get(normalized_url, timeout=5)
                                if ext_resp.status_code == 404:
                                    broken_links.add(normalized_url)
                            except:
                                broken_links.add(normalized_url)

                pages_scanned += 1
            except:
                broken_links.add(url)

    return {
        "pages_scanned": pages_scanned,
        "outbound_links": sorted(outbound_links),
        "broken_links": sorted(broken_links)
    }

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    if request.method == 'POST':
        url = request.form['url'].strip()
        if not url.startswith("http"):
            url = "https://" + url
        start_time = time.time()
        results = crawl_site(url)
        results["elapsed"] = round(time.time() - start_time, 2)
        results["start_url"] = url
    return render_template('index.html', results=results)

if __name__ == '__main__':
    app.run(debug=True)
