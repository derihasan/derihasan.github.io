#!/usr/bin/env python3
"""
Unit tests for Indonesian News Fetcher
"""

import sys
import os
from datetime import datetime, timedelta
import tempfile
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from fetch_indonesian_news import NewsItem, NewsCache, IndonesianNewsScanner


def test_news_item_creation():
    """Test NewsItem creation and URL hashing"""
    print("Testing NewsItem creation...")
    
    news = NewsItem(
        url="https://www.kompas.com/tren/read/2024/11/03/test-article",
        title="Test Article Title",
        summary="This is a test summary",
        publish_date=datetime.now(),
        source="kompas.com",
        importance_score=10
    )
    
    assert news.url_hash is not None
    assert len(news.url_hash) == 64  # SHA-256 produces 64 hex chars
    assert news.title == "Test Article Title"
    print("✓ NewsItem creation works")


def test_url_canonicalization():
    """Test URL canonicalization"""
    print("Testing URL canonicalization...")
    
    news1 = NewsItem(url="https://www.kompas.com/article/", title="Test")
    news2 = NewsItem(url="https://WWW.KOMPAS.COM/article", title="Test")
    news3 = NewsItem(url="https://www.kompas.com/article?utm_source=test", title="Test")
    
    # Same canonical URL should produce same hash
    assert news1.url_hash == news2.url_hash, "URLs with different case should match"
    
    # Different paths should produce different hashes  
    news4 = NewsItem(url="https://www.kompas.com/different", title="Test")
    assert news1.url_hash != news4.url_hash, "Different URLs should not match"
    
    print("✓ URL canonicalization works")


def test_recency_check():
    """Test time window filtering"""
    print("Testing recency check...")
    
    # Recent news
    recent_news = NewsItem(
        url="https://example.com/recent",
        title="Recent",
        publish_date=datetime.now() - timedelta(hours=1)
    )
    assert recent_news.is_recent(hours=3), "1-hour old news should be recent"
    
    # Old news
    old_news = NewsItem(
        url="https://example.com/old",
        title="Old",
        publish_date=datetime.now() - timedelta(hours=5)
    )
    assert not old_news.is_recent(hours=3), "5-hour old news should not be recent"
    
    print("✓ Recency check works")


def test_news_cache():
    """Test URL deduplication cache"""
    print("Testing news cache...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_file = f.name
    
    try:
        cache = NewsCache(cache_file=cache_file)
        
        # Test adding to cache
        test_hash = "abcd1234" * 8  # 64 char hash
        assert not cache.is_duplicate(test_hash), "New hash should not be duplicate"
        
        cache.add(test_hash)
        assert cache.is_duplicate(test_hash), "Added hash should be duplicate"
        
        # Test cache persistence
        cache2 = NewsCache(cache_file=cache_file)
        assert cache2.is_duplicate(test_hash), "Cache should persist"
        
        print("✓ News cache works")
        
    finally:
        if os.path.exists(cache_file):
            os.remove(cache_file)


def test_importance_calculation():
    """Test importance scoring"""
    print("Testing importance calculation...")
    
    scanner = IndonesianNewsScanner()
    
    # National importance
    score1 = scanner._calculate_importance(
        "Presiden Indonesia Umumkan Kebijakan Baru",
        "Presiden mengumumkan kebijakan ekonomi nasional"
    )
    assert score1 > 10, "National news should have high score"
    
    # Viral content
    score2 = scanner._calculate_importance(
        "Video Viral Heboh di Media Sosial",
        "Konten ini viral dan trending di semua platform"
    )
    assert score2 > 5, "Viral content should have decent score"
    
    # Low importance
    score3 = scanner._calculate_importance(
        "Regular Article",
        "Just a regular article"
    )
    assert score3 < score1, "Regular content should score lower"
    
    print("✓ Importance calculation works")


def test_news_card_formatting():
    """Test social media card formatting"""
    print("Testing news card formatting...")
    
    scanner = IndonesianNewsScanner()
    
    news = NewsItem(
        url="https://www.kompas.com/tren/read/2024/11/03/test",
        title="Indonesia Wins International Award",
        summary="Indonesia received prestigious award for cultural achievement.",
        publish_date=datetime.now(),
        source="kompas.com",
        importance_score=25
    )
    
    card = scanner.format_news_card(news)
    
    # Check formatting
    assert "INDONESIA WINS INTERNATIONAL AWARD" in card, "Title should be uppercase"
    assert "Image suggestion:" in card, "Should have image suggestion"
    assert "#Indonesia" in card, "Should have Indonesia hashtag"
    assert "#News" in card, "Should have News hashtag"
    assert "#Trending" in card, "Should have Trending hashtag"
    assert news.url in card, "Should include source URL"
    
    print("✓ News card formatting works")


def test_image_suggestion():
    """Test image suggestion logic"""
    print("Testing image suggestion...")
    
    scanner = IndonesianNewsScanner()
    
    # Political news
    suggestion1 = scanner._suggest_image("Presiden Indonesia", "Kebijakan pemerintah")
    assert "government" in suggestion1.lower() or "politik" in suggestion1.lower()
    
    # Sports news
    suggestion2 = scanner._suggest_image("Timnas Indonesia Menang", "Sepak bola")
    assert "sports" in suggestion2.lower() or "action" in suggestion2.lower()
    
    # Entertainment
    suggestion3 = scanner._suggest_image("Artis Indonesia", "Film baru")
    assert "celebrity" in suggestion3.lower() or "entertainment" in suggestion3.lower()
    
    print("✓ Image suggestion works")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("Running Indonesian News Fetcher Tests")
    print("="*60 + "\n")
    
    tests = [
        test_news_item_creation,
        test_url_canonicalization,
        test_recency_check,
        test_news_cache,
        test_importance_calculation,
        test_news_card_formatting,
        test_image_suggestion,
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1
    
    print("\n" + "="*60)
    if failed == 0:
        print("All tests passed! ✓")
    else:
        print(f"{failed} test(s) failed ✗")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
