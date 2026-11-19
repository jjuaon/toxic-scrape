# Our first scraping test: can we log in to X with twscrape and get tweets for one hashtag?
# (the real collection is in collect_x.py)
#
# How to run:
#   $env:X_COOKIES = "auth_token=PASTE_HERE; ct0=PASTE_HERE"
#   $env:X_USERNAME = "your_x_handle"
#   python test_twscrape.py --hashtag gaming --limit 50     (posts)
#   python test_twscrape.py --hashtag gaming --replies      (replies under a few posts)

import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from twscrape import API
from twscrape.accounts_pool import NoAccountError

DEFAULT_DB = Path.home() / ".twscrape_kmutt" / "accounts.db"
OUTPUT_DIR = Path(__file__).parent / "data" / "raw"

# no usernames or links (links have the username in them)
COLUMNS = ["platform", "topic", "id", "text", "created_at", "lang",
           "like_count", "reply_count", "retweet_count"]
# one row per reply, with the post it replied to
REPLY_COLUMNS = COLUMNS[:6] + ["like_count", "post_id", "post_text", "post_created_at",
                               "post_like_count", "post_reply_count", "post_retweet_count"]
WAIT_SECONDS = 60  # stop instead of waiting forever when rate-limited


def build_query(hashtag, days):
    now = datetime.now(timezone.utc)
    until = now.date() + timedelta(days=1)   # until: is not included, so use tomorrow
    since = now.date() - timedelta(days=days)
    query = f"#{hashtag} lang:en -filter:retweets since:{since} until:{until}"
    return query, since, until


async def check_account(api, db_path):
    cookies = os.environ.get("X_COOKIES")
    username = os.environ.get("X_USERNAME")

    if cookies and username:
        try:
            await api.pool.add_account_cookies(username, cookies)
        except ValueError as e:
            sys.exit(f"Bad X_COOKIES: {e}")
    elif cookies or username:
        sys.exit("Set both X_COOKIES and X_USERNAME, or neither.")

    accounts = await api.pool.accounts_info()
    if len(accounts) == 0:
        sys.exit(f"No saved X account in {db_path}. Set X_COOKIES and X_USERNAME first.")

    active = [a for a in accounts if a["active"]]
    if len(active) == 0:
        errors = [str(a["error_msg"]) for a in accounts]
        sys.exit("Accounts are inactive: " + "; ".join(errors) + "\nGet new cookies and try again.")


async def get_posts(api, query, limit):
    # returns (tweets, error message). keeps what we got before an error
    tweets = []
    try:
        async for tweet in api.search(query, limit=limit):
            tweets.append(tweet)
            if len(tweets) >= limit:  # search() sometimes gives a few more
                break
    except NoAccountError:
        return tweets, f"account is rate-limited or locked (waited {WAIT_SECONDS}s)"
    except Exception as e:
        return tweets, f"{type(e).__name__}: {e}"
    return tweets, None


async def get_replies(api, hashtag, days, n_posts, per_post, min_replies):
    query, _, _ = build_query(hashtag, days)
    query += f" -filter:replies min_replies:{min_replies}"
    print("Query:", query)
    print()

    pairs = []  # (post, reply)
    try:
        posts = []
        async for p in api.search(query, limit=n_posts):
            posts.append(p)
        posts = posts[:n_posts]
        print(f"Found {len(posts)} of {n_posts} posts")

        for post in posts:
            replies = []
            async for r in api.tweet_replies(post.id, limit=per_post):
                replies.append(r)
            replies = replies[:per_post]
            print(f"Post {post.id}: X says {post.replyCount} replies, we got {len(replies)}")
            for r in replies:
                if r.lang == "en":
                    pairs.append((post, r))
    except NoAccountError:
        return pairs, f"account is rate-limited or locked (waited {WAIT_SECONDS}s)"
    except Exception as e:
        return pairs, f"{type(e).__name__}: {e}"
    return pairs, None


def save_posts(tweets, hashtag, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for t in tweets:
            writer.writerow(["twitter", hashtag, t.id_str, t.rawContent, t.date.isoformat(),
                             t.lang, t.likeCount, t.replyCount, t.retweetCount])


def save_replies(pairs, hashtag, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(REPLY_COLUMNS)
        for post, r in pairs:
            writer.writerow(["twitter", hashtag, r.id_str, r.rawContent, r.date.isoformat(),
                             r.lang, r.likeCount, post.id_str, post.rawContent,
                             post.date.isoformat(), post.likeCount, post.replyCount,
                             post.retweetCount])


def print_checks(tweets, error, hashtag, limit, since, until, path):
    print(f"\nGot {len(tweets)} of {limit} tweets")
    if error:
        print("Stopped early:", error)
    if len(tweets) == 0:
        print("Failed, no tweets.")
        return False

    dates = [t.date for t in tweets]
    print("Saved to:", path)
    print(f"Dates: {min(dates):%Y-%m-%d %H:%M} to {max(dates):%Y-%m-%d %H:%M} UTC")

    # did the search give us what we asked for?
    tag = "#" + hashtag
    unique_ids = len(set(t.id_str for t in tweets))
    unique_texts = len(set(t.rawContent.strip().lower() for t in tweets))
    outside = 0
    not_en = 0
    retweets = 0
    no_tag = 0
    for t in tweets:
        if not (since <= t.date.date() < until):
            outside += 1
        if t.lang != "en":
            not_en += 1
        if t.retweetedTweet is not None:
            retweets += 1
        if tag not in t.rawContent.lower():
            no_tag += 1

    print("\nChecks (last 4 should be about 0):")
    print("  unique ids:    ", unique_ids)
    print("  unique texts:  ", unique_texts)
    print("  outside dates: ", outside)
    print("  not English:   ", not_en)
    print("  retweets:      ", retweets)
    print(f"  no {tag} in text:", no_tag)

    print("\nFirst 3 tweets:")
    for t in tweets[:3]:
        print("  -", " ".join(t.rawContent.split())[:120])

    ok = len(tweets) >= limit and unique_ids == len(tweets) and outside == 0 and retweets == 0
    if ok:
        print("\nOK, can try a bigger run.")
    else:
        print("\nCheck the numbers above.")
    return ok


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hashtag", default="gaming")    # without the #
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--replies", action="store_true")
    # only for --replies
    parser.add_argument("--posts", type=int, default=5)
    parser.add_argument("--per-post", type=int, default=50)
    parser.add_argument("--min-replies", type=int, default=20)
    args = parser.parse_args()

    sys.stdout.reconfigure(errors="replace")  # emoji can crash the Windows terminal

    hashtag = args.hashtag.lstrip("#").lower()
    if args.out:
        out = args.out
    elif args.replies:
        out = OUTPUT_DIR / f"twitter_test_{hashtag}_replies.csv"
    else:
        out = OUTPUT_DIR / f"twitter_test_{hashtag}.csv"
    args.db.parent.mkdir(parents=True, exist_ok=True)

    api = API(str(args.db), raise_when_no_account=True, wait_timeout=WAIT_SECONDS)
    await check_account(api, args.db)

    if args.replies:
        pairs, error = await get_replies(api, hashtag, args.days, args.posts,
                                         args.per_post, args.min_replies)
        if error:
            print("Stopped early:", error)
        if pairs:
            save_replies(pairs, hashtag, out)
            n_posts = len(set(post.id_str for post, _ in pairs))
            print(f"\nSaved {len(pairs)} English replies from {n_posts} posts to {out}")
        else:
            print("\nFailed, no replies.")
        sys.exit(0 if pairs and not error else 1)

    query, since, until = build_query(hashtag, args.days)
    print("Query:", query)
    tweets, error = await get_posts(api, query, args.limit)
    if tweets:
        save_posts(tweets, hashtag, out)
    ok = print_checks(tweets, error, hashtag, args.limit, since, until, out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
