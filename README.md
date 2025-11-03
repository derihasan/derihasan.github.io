# derihasan.github.io

## Indonesian Trending News Automation

This repository includes an automated system that discovers trending Indonesian news every 3 hours.

### Features

- **Automated Discovery**: Runs every 3 hours via GitHub Actions
- **Multiple Sources**: Fetches from major Indonesian news sites (Detik, Kompas, CNN Indonesia, etc.)
- **Smart Filtering**: Only surfaces news from the last 3 hours
- **Deduplication**: Uses SHA-256 hashing to prevent duplicate URLs (24-hour cache, max 500 items)
- **Intelligent Ranking**: Prioritizes by national importance > virality > freshness
- **Ready-to-Post**: Outputs formatted social media news cards

### How It Works

1. **Scheduled Execution**: GitHub Actions workflow runs every 3 hours
2. **Multi-Source Fetching**: Queries 5+ diverse sources including RSS feeds and trending pages
3. **Date Filtering**: Parses publish dates and HTTP headers, discards anything older than 3 hours
4. **Deduplication**: Maintains a cache of seen URLs using SHA-256 hashes
5. **Scoring & Ranking**: Calculates importance based on:
   - National interest keywords (government, elections, etc.)
   - Virality indicators (trending, viral, etc.)
   - Topic relevance (sports, economy, entertainment, etc.)
   - Freshness of content
6. **Output Generation**: Creates formatted social media cards with:
   - ALL CAPS headline
   - Image suggestion
   - Engaging summary
   - Source link
   - Relevant hashtags

### Manual Execution

To test the workflow manually:
1. Go to Actions tab
2. Select "Indonesian Trending News" workflow
3. Click "Run workflow"

### Requirements

- Python 3.11+
- Dependencies listed in `requirements.txt`

### Output Format

```
[HEADLINE IN ALL CAPS]

Image suggestion: [Relevant image description]
[One-sentence engaging summary]
Source: [URL]

#Indonesia #News #Trending
```

If no significant news is found:
```
No significant updates in the past 3 hours.
```