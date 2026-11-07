# Which Social Media Platform Is the Most Toxic?

A text analytics final project at KMUTT.

We collect comments from social media, score how toxic they are, and compare the results across platforms.

## Objectives

1. Measure and compare the level of toxicity in comments across social media platforms.
2. Find the most common type of toxicity on each platform.
3. Compare a simple bad-word list with an AI toxicity model (Detoxify) and show what the word list misses.

## How it works

1. **Collect** comments from each platform.
2. **Clean** the text by removing links, mentions, duplicates and non-English comments.
3. **Score** each comment with Detoxify and the bad-word list.
4. **Compare** the platforms and the two scoring methods.

## Project status

The project is in progress. So far we have a working test for collecting X (Twitter) data.

| Step | Status |
|---|---|
| Test X data collection | Done |
| Choose the final platforms and topic | Not decided |
| Collect the full dataset | Not started |
| Clean the data | Not started |
| Score toxicity | Not started |
| Analyse results and write the report | Not started |

## Files

| File | Purpose |
|---|---|
| `test_twscrape.py` | Collects X posts by hashtag, or the comments under those posts |
| `data/raw/` | Collected CSV files (not committed to Git) |

## Try the X collector

You need Python and an X account. Use a dedicated account, because X can restrict accounts that scrape.

**1. Install twscrape**

```powershell
pip install twscrape
```

**2. Add your login (first run only)**

Log in to x.com, then copy `auth_token` and `ct0` from your browser's DevTools (Application > Cookies > `https://x.com`).

Set them in your PowerShell window, in the same window you use to run the script:

```powershell
$env:X_COOKIES = "auth_token=PASTE_HERE; ct0=PASTE_HERE"
$env:X_USERNAME = "your_x_handle_without_the_at_sign"
```

**3. Collect data**

```powershell
# 50 posts with #gaming from the last 7 days
python test_twscrape.py

# Comments under posts with #politics
python test_twscrape.py --replies --hashtag politics
```

Results are saved to `data/raw/` as CSV files.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--hashtag` | `gaming` | Hashtag to search, without the `#` |
| `--days` | `7` | How many days to look back |
| `--limit` | `50` | Number of posts to collect |
| `--replies` | Off | Collect comments instead of posts |
| `--posts` | `5` | With `--replies`: number of posts to use |
| `--per-post` | `50` | With `--replies`: maximum comments per post |
| `--min-replies` | `20` | With `--replies`: minimum comments a post needs |
| `--out` | Automatic | Output CSV path |
| `--db` | `~/.twscrape_kmutt/accounts.db` | Saved login file |

## Important notes

- **Keep cookies private.** They give full access to the account. Never put them in this script, the README, a notebook or a Git commit. Set them only in the terminal.
- **Protect the data.** The CSV files contain post links that include usernames, so keep them out of the report and slides.
- **Know the risks.** twscrape uses X's private API, and scraping without written consent breaks X's terms. The account can be blocked, and the tool can stop working if X changes its API. We will disclose this method in the report.
- **Collect slowly.** Start with small runs, and wait at least 15 minutes after a rate limit.
