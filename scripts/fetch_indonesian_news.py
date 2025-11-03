#!/usr/bin/env python3
"""
Indonesian Trending News Fetcher

Fetches trending Indonesian news every 3 hours from multiple sources,
deduplicates, filters by time, and outputs formatted social media cards.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin
import time

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# Configuration
CACHE_FILE = "news_cache.json"
MAX_CACHE_SIZE = 500
TIME_WINDOW_HOURS = 3
OUTPUT_FILE = "news_output.txt"

# Search queries to run each cycle
SEARCH_QUERIES = [
    "berita trending Indonesia",
    "berita populer site:kompas.com",
    "viral site:detik.com",
    "berita terbaru site:cnnindonesia.com",
    "trending topic Indonesia"
]

# Popular Indonesian news sites
NEWS_SOURCES = [
    "https://www.detik.com/terpopuler",
    "https://www.kompas.com/terpopuler",
    "https://www.cnnindonesia.com/",
    "https://www.tribunnews.com/",
    "https://nasional.tempo.co/"
]


class NewsItem:
    """Represents a single news item"""
    
    def __init__(self, url: str, title: str, summary: str = "", 
                 publish_date: Optional[datetime] = None, 
                 source: str = "", importance_score: int = 0):
        self.url = url
        self.canonical_url = self._canonicalize_url(url)
        self.url_hash = self._hash_url(self.canonical_url)
        self.title = title
        self.summary = summary
        self.publish_date = publish_date or datetime.now()
        self.source = source
        self.importance_score = importance_score
        
    def _canonicalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        parsed = urlparse(url)
        # Remove query parameters and fragments, lowercase domain
        canonical = f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path}"
        # Remove trailing slashes
        canonical = canonical.rstrip('/')
        return canonical
    
    def _hash_url(self, url: str) -> str:
        """Generate SHA-256 hash of URL"""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()
    
    def is_recent(self, hours: int = TIME_WINDOW_HOURS) -> bool:
        """Check if news is within the time window"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return self.publish_date >= cutoff
    
    def to_dict(self) -> dict:
        """Convert to dictionary for caching"""
        return {
            'url': self.url,
            'url_hash': self.url_hash,
            'title': self.title,
            'summary': self.summary,
            'publish_date': self.publish_date.isoformat(),
            'source': self.source,
            'importance_score': self.importance_score
        }


class NewsCache:
    """Manages URL deduplication cache with 24-hour window"""
    
    def __init__(self, cache_file: str = CACHE_FILE, max_size: int = MAX_CACHE_SIZE):
        self.cache_file = cache_file
        self.max_size = max_size
        self.cache = self._load_cache()
        
    def _load_cache(self) -> Dict[str, float]:
        """Load cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    # Clean up old entries (> 24 hours)
                    cutoff = time.time() - (24 * 60 * 60)
                    return {k: v for k, v in data.items() if v > cutoff}
            except Exception as e:
                print(f"Warning: Could not load cache: {e}", file=sys.stderr)
        return {}
    
    def _save_cache(self):
        """Save cache to file"""
        try:
            # Keep only the most recent entries if we exceed max size
            if len(self.cache) > self.max_size:
                sorted_items = sorted(self.cache.items(), key=lambda x: x[1], reverse=True)
                self.cache = dict(sorted_items[:self.max_size])
            
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}", file=sys.stderr)
    
    def is_duplicate(self, url_hash: str) -> bool:
        """Check if URL hash exists in cache"""
        return url_hash in self.cache
    
    def add(self, url_hash: str):
        """Add URL hash to cache with current timestamp"""
        self.cache[url_hash] = time.time()
        self._save_cache()


class IndonesianNewsScanner:
    """Main news scanner class"""
    
    def __init__(self):
        self.cache = NewsCache()
        self.news_items: List[NewsItem] = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_from_rss_feeds(self):
        """Fetch news from Indonesian RSS feeds"""
        rss_feeds = [
            "https://www.detik.com/feed/",
            "https://www.kompas.com/rss/",
            "https://www.cnnindonesia.com/rss/",
        ]
        
        for feed_url in rss_feeds:
            try:
                response = self.session.get(feed_url, timeout=10)
                if response.status_code == 200:
                    self._parse_rss(response.text, feed_url)
            except Exception as e:
                print(f"Error fetching RSS {feed_url}: {e}", file=sys.stderr)
    
    def _parse_rss(self, content: str, source_url: str):
        """Parse RSS feed content"""
        try:
            soup = BeautifulSoup(content, 'xml')
            items = soup.find_all('item')[:20]  # Limit to recent items
            
            for item in items:
                try:
                    title_tag = item.find('title')
                    link_tag = item.find('link')
                    pub_date_tag = item.find('pubDate')
                    description_tag = item.find('description')
                    
                    if not title_tag or not link_tag:
                        continue
                    
                    title = title_tag.text.strip()
                    url = link_tag.text.strip()
                    
                    # Parse publish date
                    publish_date = None
                    if pub_date_tag:
                        try:
                            publish_date = date_parser.parse(pub_date_tag.text)
                        except:
                            pass
                    
                    summary = ""
                    if description_tag:
                        # Clean HTML from description
                        desc_soup = BeautifulSoup(description_tag.text, 'html.parser')
                        summary = desc_soup.get_text().strip()[:200]
                    
                    # Calculate importance score
                    importance = self._calculate_importance(title, summary)
                    
                    news_item = NewsItem(
                        url=url,
                        title=title,
                        summary=summary,
                        publish_date=publish_date,
                        source=urlparse(source_url).netloc,
                        importance_score=importance
                    )
                    
                    # Check if recent and not duplicate
                    if news_item.is_recent() and not self.cache.is_duplicate(news_item.url_hash):
                        self.news_items.append(news_item)
                        
                except Exception as e:
                    print(f"Error parsing RSS item: {e}", file=sys.stderr)
                    continue
                    
        except Exception as e:
            print(f"Error parsing RSS: {e}", file=sys.stderr)
    
    def fetch_from_trending_pages(self):
        """Scrape trending/popular pages directly"""
        for source_url in NEWS_SOURCES:
            try:
                response = self.session.get(source_url, timeout=10)
                if response.status_code == 200:
                    self._parse_trending_page(response.text, source_url)
            except Exception as e:
                print(f"Error fetching {source_url}: {e}", file=sys.stderr)
    
    def _parse_trending_page(self, content: str, source_url: str):
        """Parse trending page HTML"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Look for common article patterns
            articles = soup.find_all(['article', 'div'], class_=re.compile(r'article|item|post|news', re.I))[:15]
            
            if not articles:
                # Try finding links in common news containers
                articles = soup.find_all('a', href=re.compile(r'/(news|berita|nasional|viral|trending)', re.I))[:15]
            
            for article in articles:
                try:
                    # Find title and link
                    if article.name == 'a':
                        link = article.get('href')
                        title_elem = article.find(['h1', 'h2', 'h3', 'h4']) or article
                        title = title_elem.get_text().strip()
                    else:
                        link_elem = article.find('a')
                        if not link_elem:
                            continue
                        link = link_elem.get('href')
                        title_elem = article.find(['h1', 'h2', 'h3', 'h4'])
                        title = title_elem.get_text().strip() if title_elem else link_elem.get_text().strip()
                    
                    if not link or not title or len(title) < 10:
                        continue
                    
                    # Make absolute URL
                    if link.startswith('/'):
                        link = urljoin(source_url, link)
                    
                    # Get summary if available
                    summary = ""
                    summary_elem = article.find(['p', 'div'], class_=re.compile(r'summary|excerpt|description', re.I))
                    if summary_elem:
                        summary = summary_elem.get_text().strip()[:200]
                    
                    # Try to find publish date
                    publish_date = None
                    time_elem = article.find(['time', 'span'], class_=re.compile(r'date|time|publish', re.I))
                    if time_elem:
                        try:
                            datetime_attr = time_elem.get('datetime') or time_elem.get_text()
                            publish_date = date_parser.parse(datetime_attr)
                        except:
                            pass
                    
                    importance = self._calculate_importance(title, summary)
                    
                    news_item = NewsItem(
                        url=link,
                        title=title,
                        summary=summary,
                        publish_date=publish_date,
                        source=urlparse(source_url).netloc,
                        importance_score=importance
                    )
                    
                    # Only add if recent and not duplicate
                    if news_item.is_recent() and not self.cache.is_duplicate(news_item.url_hash):
                        self.news_items.append(news_item)
                        
                except Exception as e:
                    print(f"Error parsing article: {e}", file=sys.stderr)
                    continue
                    
        except Exception as e:
            print(f"Error parsing page: {e}", file=sys.stderr)
    
    def _calculate_importance(self, title: str, summary: str) -> int:
        """Calculate importance score based on keywords"""
        text = (title + " " + summary).lower()
        score = 0
        
        # National importance keywords
        national_keywords = [
            'presiden', 'menteri', 'nasional', 'indonesia', 'dpr', 'pemerintah',
            'negara', 'jakarta', 'ibu kota', 'kpu', 'pemilu', 'pilpres'
        ]
        for keyword in national_keywords:
            if keyword in text:
                score += 10
        
        # Virality indicators
        viral_keywords = [
            'viral', 'trending', 'heboh', 'ramai', 'populer', 'hits',
            'sensation', 'kontroversial', 'fenomenal', 'gempar'
        ]
        for keyword in viral_keywords:
            if keyword in text:
                score += 8
        
        # Topic interest
        topic_keywords = [
            'bola', 'sepak bola', 'timnas', 'juara', 'medali', 'olimpiade',
            'ekonomi', 'rupiah', 'investasi', 'ekspor', 'saham',
            'artis', 'selebriti', 'film', 'musik', 'penyanyi',
            'bencana', 'gempa', 'banjir', 'kebakaran', 'kecelakaan',
            'prestasi', 'penghargaan', 'rekor', 'achievement'
        ]
        for keyword in topic_keywords:
            if keyword in text:
                score += 5
        
        # Breaking news indicator
        if any(word in text for word in ['breaking', 'terkini', 'baru', 'update']):
            score += 3
        
        return score
    
    def rank_news(self):
        """Rank news by importance > virality > freshness"""
        self.news_items.sort(key=lambda x: (
            x.importance_score,  # Primary: importance
            x.publish_date.timestamp() if x.publish_date else 0  # Secondary: freshness
        ), reverse=True)
    
    def get_top_news(self, count: int = 1) -> List[NewsItem]:
        """Get top N news items"""
        return self.news_items[:count]
    
    def format_news_card(self, news: NewsItem) -> str:
        """Format news item as social media card"""
        # Make headline punchy and all caps
        headline = news.title.upper()
        if len(headline) > 100:
            headline = headline[:97] + "..."
        
        # Get domain for source attribution
        source_domain = urlparse(news.url).netloc.replace('www.', '')
        
        # Create engaging summary
        if news.summary:
            summary = news.summary
            if len(summary) > 150:
                summary = summary[:147] + "..."
        else:
            summary = "Breaking news from Indonesia - check the link for full details!"
        
        # Suggest image based on content
        image_suggestion = self._suggest_image(news.title, news.summary)
        
        # Format card
        card = f"""
{headline}

Image suggestion: {image_suggestion}
{summary}
Source: {news.url}

#Indonesia #News #Trending
"""
        return card.strip()
    
    def _suggest_image(self, title: str, summary: str) -> str:
        """Suggest image type based on content"""
        text = (title + " " + summary).lower()
        
        if any(word in text for word in ['presiden', 'menteri', 'pemerintah', 'politik']):
            return "High-quality image of Indonesian government/politics (official photo, no watermark)"
        elif any(word in text for word in ['bola', 'timnas', 'olahraga', 'juara']):
            return "Dynamic sports action photo (match moment, celebration, athlete)"
        elif any(word in text for word in ['artis', 'selebriti', 'film', 'musik']):
            return "Professional photo of celebrity/entertainment figure"
        elif any(word in text for word in ['ekonomi', 'bisnis', 'rupiah', 'saham']):
            return "Clean business/economy graphic or chart"
        elif any(word in text for word in ['bencana', 'gempa', 'banjir']):
            return "Respectful documentation photo of the event"
        else:
            return "Relevant high-quality image matching the story (avoid watermarks)"
    
    def run(self):
        """Main execution flow"""
        print("Starting Indonesian trending news scan...", file=sys.stderr)
        print(f"Time window: Last {TIME_WINDOW_HOURS} hours", file=sys.stderr)
        
        # Fetch from multiple sources
        print("Fetching from RSS feeds...", file=sys.stderr)
        self.fetch_from_rss_feeds()
        
        print("Fetching from trending pages...", file=sys.stderr)
        self.fetch_from_trending_pages()
        
        print(f"Found {len(self.news_items)} recent items", file=sys.stderr)
        
        # Remove duplicates (already handled by cache check, but just in case)
        unique_items = {}
        for item in self.news_items:
            if item.url_hash not in unique_items:
                unique_items[item.url_hash] = item
        self.news_items = list(unique_items.values())
        
        print(f"After deduplication: {len(self.news_items)} unique items", file=sys.stderr)
        
        # Rank news
        self.rank_news()
        
        # Get top news
        top_news = self.get_top_news(count=1)
        
        # Generate output
        output = ""
        if top_news:
            news = top_news[0]
            output = self.format_news_card(news)
            # Add to cache
            self.cache.add(news.url_hash)
            print(f"Selected news with score {news.importance_score}", file=sys.stderr)
        else:
            output = "No significant updates in the past 3 hours."
        
        # Write output
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(output)
        
        print(f"\nOutput written to {OUTPUT_FILE}", file=sys.stderr)
        print("\n" + "="*60, file=sys.stderr)
        print(output)
        print("="*60, file=sys.stderr)


def main():
    """Entry point"""
    scanner = IndonesianNewsScanner()
    scanner.run()


if __name__ == "__main__":
    main()
