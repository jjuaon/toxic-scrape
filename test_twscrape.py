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
COLUMNS = [
    "platform", "topic", "id", "url", "text", "created_at", "lang",
    "like_count", "reply_count", "retweet_count",
]
# Each row is one comment, with the post it replied to repeated alongside it.
REPLY_COLUMNS = COLUMNS[:7] + [
    "like_count", "post_id", "post_url", "post_text", "post_created_at",
    "post_like_count", "post_reply_count", "post_retweet_count",
]
WAIT_SECONDS = 60  # give up instead of waiting forever when rate-limited


def build_query(hashtag, days, now=None):
    """Return the X search query and the start/end dates of the window."""
    now = now or datetime.now(timezone.utc)
    # X's until: date is exclusive, so use tomorrow to include today's tweets.
    until = now.date() + timedelta(days=1)
    since = now.date() - timedelta(days=days)
    query = f"#{hashtag} lang:en -filter:retweets since:{since} until:{until}"
    return query, since, until


async def setup_account(api, db_path):
    """Save the login from the environment, or check that one is already saved."""
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
    if not accounts:
        sys.exit(
            f"No saved X account in {db_path}.\n"
            "Set X_COOKIES and X_USERNAME first (see the top of this script)."
        )

    active = [a for a in accounts if a["active"]]
    if not active:
        reasons = "; ".join(str(a["error_msg"]) for a in accounts)
        sys.exit(f"Saved accounts are inactive: {reasons}\nRefresh the cookies and retry.")


async def collect(api, query, limit):
    """Return (tweets, error). Tweets found before a failure are kept."""
    tweets = []
    try:
        async for tweet in api.search(query, limit=limit):
            tweets.append(tweet)
            if len(tweets) >= limit:  # search() may return a little over the limit
                break
    except NoAccountError:
        return tweets, f"account is rate-limited or locked (waited {WAIT_SECONDS}s)"
    except Exception as e:
        return tweets, f"{type(e).__name__}: {e}"
    return tweets, None


async def collect_replies(api, hashtag, days, posts, per_post, min_replies):
    """Return ((post, English reply) pairs, error). Pairs found before a failure are kept."""
    window, _, _ = build_query(hashtag, days)
    query = f"{window} -filter:replies min_replies:{min_replies}"
    print(f"Query: {query}\n")

    replies = []
    try:
        found = [p async for p in api.search(query, limit=posts)][:posts]
        print(f"Found {len(found)} of {posts} posts")
        for post in found:
            got = [r async for r in api.tweet_replies(post.id, limit=per_post)][:per_post]
            print(f"Post {post.id}: X shows {post.replyCount} replies, collected {len(got)}")
            replies.extend((post, r) for r in got if r.lang == "en")
    except NoAccountError:
        return replies, f"account is rate-limited or locked (waited {WAIT_SECONDS}s)"
    except Exception as e:
        return replies, f"{type(e).__name__}: {e}"
    return replies, None


def save_csv(tweets, hashtag, path):
    """Save posts. URLs contain usernames, so keep them out of the report and slides."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for t in tweets:
            writer.writerow([
                "twitter", hashtag, t.id_str, t.url, t.rawContent, t.date.isoformat(), t.lang,
                t.likeCount, t.replyCount, t.retweetCount,
            ])


def save_replies_csv(pairs, hashtag, path):
    """Save one row per comment, with its post's details. URLs contain usernames."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(REPLY_COLUMNS)
        for post, r in pairs:
            writer.writerow([
                "twitter", hashtag, r.id_str, r.url, r.rawContent, r.date.isoformat(), r.lang,
                r.likeCount, post.id_str, post.url, post.rawContent, post.date.isoformat(),
                post.likeCount, post.replyCount, post.retweetCount,
            ])


def check_quality(tweets, hashtag, since, until):
    """Return counts that show whether the search returned what was asked for."""
    tag = f"#{hashtag}".lower()
    return {
        "unique_ids": len({t.id_str for t in tweets}),
        "unique_texts": len({t.rawContent.strip().lower() for t in tweets}),
        "outside_window": sum(not since <= t.date.date() < until for t in tweets),
        "not_english": sum(t.lang != "en" for t in tweets),
        "retweets": sum(t.retweetedTweet is not None for t in tweets),
        "no_hashtag_in_text": sum(tag not in t.rawContent.lower() for t in tweets),
    }


def print_report(tweets, error, hashtag, limit, since, until, path):
    print(f"\nCollected {len(tweets)} of {limit} requested")
    if error:
        print(f"Stopped early: {error}")
    if not tweets:
        print("RESULT: FAILED, no tweets to check.")
        return False

    dates = [t.date for t in tweets]
    print(f"Saved to:   {path}")
    print(f"Date range: {min(dates):%Y-%m-%d %H:%M} to {max(dates):%Y-%m-%d %H:%M} UTC")

    q = check_quality(tweets, hashtag, since, until)
    print("\nChecks (the last four should be 0 or close to it):")
    print(f"  Unique tweet IDs:   {q['unique_ids']}")
    print(f"  Unique texts:       {q['unique_texts']}")
    print(f"  Outside the window: {q['outside_window']}")
    print(f"  Not English:        {q['not_english']}")
    print(f"  Retweets:           {q['retweets']}")
    print(f"  No #{hashtag} in text: {q['no_hashtag_in_text']}")

    print("\nSample tweets:")
    for t in tweets[:3]:
        print(f"  - {' '.join(t.rawContent.split())[:120]}")

    ok = (
        len(tweets) >= limit
        and q["unique_ids"] == len(tweets)
        and q["outside_window"] == 0
        and q["retweets"] == 0
    )
    print("\nRESULT:", "PASSED, safe to try a larger run." if ok else "CHECK the numbers above.")
    return ok


async def main():
    parser = argparse.ArgumentParser(description="Test hashtag collection with twscrape.")
    parser.add_argument("--hashtag", default="gaming", help="without the # (default: gaming)")
    parser.add_argument("--days", type=int, default=7, help="days to look back (default: 7)")
    parser.add_argument("--limit", type=int, default=50, help="tweets to collect (default: 50)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="saved login file")
    parser.add_argument("--out", type=Path, help="output CSV path")
    parser.add_argument("--replies", action="store_true", help="collect replies instead of posts")
    parser.add_argument("--posts", type=int, default=5, help="replies mode: posts to use (default: 5)")
    parser.add_argument("--per-post", type=int, default=50, help="replies mode: max replies per post (default: 50)")
    parser.add_argument("--min-replies", type=int, default=20, help="replies mode: min replies a post needs (default: 20)")
    args = parser.parse_args()

    # Windows consoles can crash when printing emoji from tweets.
    sys.stdout.reconfigure(errors="replace")

    hashtag = args.hashtag.lstrip("#").lower()
    suffix = "_replies" if args.replies else ""
    out = args.out or OUTPUT_DIR / f"twitter_test_{hashtag}{suffix}.csv"
    args.db.parent.mkdir(parents=True, exist_ok=True)

    api = API(str(args.db), raise_when_no_account=True, wait_timeout=WAIT_SECONDS)
    await setup_account(api, args.db)

    if args.replies:
        replies, error = await collect_replies(
            api, hashtag, args.days, args.posts, args.per_post, args.min_replies
        )
        if error:
            print(f"Stopped early: {error}")
        if replies:
            save_replies_csv(replies, hashtag, out)
            n_posts = len({post.id_str for post, _ in replies})
            print(f"\nSaved {len(replies)} English replies from {n_posts} posts to {out}")
        else:
            print("\nRESULT: FAILED, no replies collected.")
        sys.exit(0 if replies and not error else 1)

    query, since, until = build_query(hashtag, args.days)
    print(f"Query: {query}")

    tweets, error = await collect(api, query, args.limit)
    if tweets:
        save_csv(tweets, hashtag, out)
    ok = print_report(tweets, error, hashtag, args.limit, since, until, out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
