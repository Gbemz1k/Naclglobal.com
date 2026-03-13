"""
Fetches live crude oil prices and Nigeria energy news, saves to .tmp/oil_data.json.
Run: python tools/fetch_oil_data.py
"""
import json, os, re, sys, datetime
from urllib.request import urlopen, Request
from html.parser import HTMLParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT = os.path.join(PROJECT_ROOT, '.tmp', 'oil_data.json')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self._skip = False
    def handle_data(self, data):
        if not self._skip:
            self.text.append(data.strip())
    def get_text(self):
        return ' '.join(t for t in self.text if t)


def fetch_url(url, timeout=15):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', errors='replace')


def scrape_oil_prices():
    """Scrape oil prices from oil-price.net (no API key needed)."""
    prices = {}
    try:
        html = fetch_url('https://www.oil-price.net/')
        # Look for WTI and Brent patterns
        wti_match = re.search(r'WTI[^$]*?\$\s*([\d.]+)', html)
        brent_match = re.search(r'Brent[^$]*?\$\s*([\d.]+)', html)
        if wti_match:
            prices['wti'] = float(wti_match.group(1))
        if brent_match:
            prices['brent'] = float(brent_match.group(1))
    except Exception as e:
        print(f'  oil-price.net failed: {e}')

    if not prices.get('wti') or not prices.get('brent'):
        try:
            html = fetch_url('https://tradingeconomics.com/commodity/crude-oil')
            p = TextExtractor()
            p.feed(html)
            text = p.get_text()
            wti_m = re.search(r'(?:WTI|Crude Oil).*?([\d]{2,3}\.[\d]{1,2})', text)
            if wti_m and 'wti' not in prices:
                prices['wti'] = float(wti_m.group(1))
        except Exception as e:
            print(f'  tradingeconomics failed: {e}')

    if not prices.get('brent'):
        try:
            html = fetch_url('https://tradingeconomics.com/commodity/brent-crude-oil')
            p = TextExtractor()
            p.feed(html)
            text = p.get_text()
            brent_m = re.search(r'([\d]{2,3}\.[\d]{1,2})', text)
            if brent_m:
                prices['brent'] = float(brent_m.group(1))
        except Exception as e:
            print(f'  tradingeconomics brent failed: {e}')

    # Bonny Light estimate (Nigerian benchmark, ~Brent + $1-3)
    if prices.get('brent'):
        prices['bonny_light'] = round(prices['brent'] + 1.5, 2)

    # Natural gas
    try:
        html = fetch_url('https://tradingeconomics.com/commodity/natural-gas')
        p = TextExtractor()
        p.feed(html)
        text = p.get_text()
        ng_m = re.search(r'([\d]{1,2}\.[\d]{1,3})', text)
        if ng_m:
            prices['natural_gas'] = float(ng_m.group(1))
    except Exception as e:
        print(f'  natural gas failed: {e}')

    return prices


def scrape_news():
    """Scrape energy news headlines from Google News RSS."""
    articles = []
    feeds = [
        ('https://news.google.com/rss/search?q=Nigeria+oil+gas+upstream+2026&hl=en-US&gl=US&ceid=US:en', 'Nigeria Oil & Gas'),
        ('https://news.google.com/rss/search?q=crude+oil+price+forecast+2026&hl=en-US&gl=US&ceid=US:en', 'Oil Markets'),
    ]
    for feed_url, category in feeds:
        try:
            xml = fetch_url(feed_url)
            items = re.findall(r'<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>.*?<source[^>]*>(.*?)</source>.*?</item>', xml, re.DOTALL)
            for title, link, pub_date, source in items[:4]:
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title).strip()
                title = re.sub(r'<[^>]+>', '', title)
                articles.append({
                    'title': title,
                    'url': link.strip(),
                    'source': re.sub(r'<[^>]+>', '', source).strip(),
                    'date': pub_date.strip(),
                    'category': category
                })
        except Exception as e:
            print(f'  News feed ({category}) failed: {e}')
    return articles[:8]


def main():
    print('Fetching oil prices...')
    prices = scrape_oil_prices()
    print(f'  Prices: {prices}')

    print('Fetching news...')
    news = scrape_news()
    print(f'  Got {len(news)} articles')

    data = {
        'prices': prices,
        'news': news,
        'updated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f'Saved to {OUTPUT}')


if __name__ == '__main__':
    main()
