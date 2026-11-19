# Collect X posts and replies for our 6 topics (uses twscrape).
#
# How to run (inside this folder):
#   python collect_x.py login                                                     (save cookies once)
#   python collect_x.py collect --since 2026-11-09 --until 2026-11-16 --dry-run   (only print the searches)
#   python collect_x.py collect --since 2026-11-09 --until 2026-11-16
#   python collect_x.py summary --out-dir data/raw                                (makes combined.csv)
#
# If the account gets rate-limited, wait 15 min and run the same command again.
# Files that are already finished are skipped.

import argparse
import asyncio
import csv
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".twscrape_kmutt" / "accounts.db"

TOPICS = {
    "us_politics": ["uspolitics", "republicans", "democrats"],
    "kpop": ["bts", "blackpink", "kpop"],
    "movies": ["movies", "film", "netflix"],
    "tech": ["ai", "tech", "iphone"],
    "pets": ["pets", "catlovers", "doglovers"],
    "food": ["recipe", "cooking", "foodie"],
}
LEVEL = {"us_politics": "high", "kpop": "high", "movies": "mid",
         "tech": "mid", "pets": "low", "food": "low"}

# no usernames / links (privacy)
COLUMNS = ["topic", "level", "hashtag", "type", "tweet_id", "parent_id", "text",
           "created_at", "lang", "like_count", "reply_count", "retweet_count", "parent_text"]


def utc_ts(day):
    d = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    return int(d.timestamp())


def posts_query(tag, since, until):
    # since_time/until_time instead of since:/until: because since:/until: uses the
    # account's time zone and our day windows overlapped (first pets run)
    q = f"#{tag} lang:en -filter:retweets -filter:replies"
    q += f" since_time:{utc_ts(since)} until_time:{utc_ts(until)}"
    return q


def parents_query(tag, since, until, min_replies):
    return posts_query(tag, since, until) + f" min_replies:{min_replies}"


def post_row(topic, tag, t):
    return [topic, LEVEL[topic], tag, "post", t.id_str, "", t.rawContent,
            t.date.isoformat(), t.lang, t.likeCount, t.replyCount, t.retweetCount, ""]


def reply_row(topic, tag, post, r):
    return [topic, LEVEL[topic], tag, "reply", r.id_str, post.id_str, r.rawContent,
            r.date.isoformat(), r.lang, r.likeCount, r.replyCount, r.retweetCount,
            post.rawContent]


def get_days(since, until):
    days = []
    d = date.fromisoformat(since)
    end = date.fromisoformat(until)
    while d < end:
        days.append((d.isoformat(), (d + timedelta(days=1)).isoformat()))
        d += timedelta(days=1)
    return days


async def search_each_day(api, since, until, make_query, total):
    # X search returns newest tweets first, so searching the whole week at once
    # only got the last 1-2 days (pilot run). We search day by day instead.
    days = get_days(since, until)
    per_day = math.ceil(total / len(days))
    found = []
    seen = set()
    for d1, d2 in days:
        if len(found) >= total:
            break
        tweets = []
        async for t in api.search(make_query(d1, d2), limit=per_day):
            tweets.append(t)
        tweets = tweets[:per_day]
        n_new = 0
        for t in tweets:
            if t.id not in seen:
                seen.add(t.id)
                found.append(t)
                n_new += 1
        print(f"    {d1}: {n_new} of {per_day}")
    return found


async def get_posts(api, topic, tag, args, path):
    def make_query(s, u):
        return posts_query(tag, s, u)

    posts = await search_each_day(api, args.since, args.until, make_query, args.posts_per_tag)

    # write to .part first and rename at the end, so a stopped run doesn't leave a half file
    part = path.with_suffix(".part")
    with open(part, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for t in posts:
            writer.writerow(post_row(topic, tag, t))
    os.replace(part, path)
    return len(posts)


async def get_replies(api, topic, tag, args, path):
    def make_query(s, u):
        return parents_query(tag, s, u, args.min_replies)

    # 1 parent post per day, so one long thread can't take over the whole topic
    parents = await search_each_day(api, args.since, args.until, make_query, args.reply_posts)
    print(f"  found {len(parents)} parent posts")

    total = 0
    part = path.with_suffix(".part")
    with open(part, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for post in parents:
            kept = 0
            # ask for 3x more because some are replies to other replies or not English
            async for r in api.tweet_replies(post.id, limit=args.per_post * 3):
                if r.inReplyToTweetId != post.id or r.id == post.id or r.lang != "en":
                    continue
                writer.writerow(reply_row(topic, tag, post, r))
                f.flush()
                kept += 1
                if kept >= args.per_post:
                    break
            print(f"    post {post.id}: kept {kept} replies")
            total += kept
    os.replace(part, path)
    return total


async def check_account(api, db_path):
    cookies = os.environ.get("X_COOKIES")
    username = os.environ.get("X_USERNAME")
    if cookies and username:
        await api.pool.add_account_cookies(username, cookies)
    elif cookies or username:
        sys.exit("Set both X_COOKIES and X_USERNAME, or neither.")

    accounts = await api.pool.accounts_info()
    active = [a for a in accounts if a["active"]]
    if len(active) == 0:
        sys.exit(f"No active X account in {db_path}. Run: python collect_x.py login")


async def collect(args):
    if args.type == "both":
        kinds = ["post", "reply"]
    else:
        kinds = [args.type]

    jobs = []
    for topic, tags in TOPICS.items():
        if args.topics and topic not in args.topics:
            continue
        for tag in tags:
            for kind in kinds:
                jobs.append((topic, tag, kind))

    if args.dry_run:
        for topic, tag, kind in jobs:
            if kind == "post":
                q = posts_query(tag, args.since, args.until)
            else:
                q = parents_query(tag, args.since, args.until, args.min_replies)
            print(f"[{topic}] {kind}: {q}")
        print(f"\n{len(jobs)} jobs. Nothing was sent to X.")
        return

    from twscrape import API
    from twscrape.accounts_pool import NoAccountError

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    api = API(str(args.db), raise_when_no_account=True, wait_timeout=args.wait)
    await check_account(api, args.db)

    for i, (topic, tag, kind) in enumerate(jobs, 1):
        path = out / f"{topic}__{tag}__{kind}.csv"
        if path.exists():
            print(f"[{i}/{len(jobs)}] skip, already done: {path.name}")
            continue
        print(f"[{i}/{len(jobs)}] {topic} #{tag} {kind}")
        try:
            if kind == "post":
                n = await get_posts(api, topic, tag, args, path)
            else:
                n = await get_replies(api, topic, tag, args, path)
            print(f"  saved {n} rows to {path.name}")
        except NoAccountError:
            print(f"\nRate-limited (waited {args.wait}s). Wait 15 min and run again.")
            sys.exit(1)
        except Exception as e:
            print(f"  error: {type(e).__name__}: {e} (will try again next run)")

    print(f"\nDone. Next run: python collect_x.py summary --out-dir {args.out_dir}")


def summary(args):
    import pandas as pd

    out = Path(args.out_dir)
    files = sorted(out.glob("*__*__*.csv"))
    if not files:
        sys.exit(f"No collected files in {out}")

    dfs = []
    for p in files:
        dfs.append(pd.read_csv(p, dtype={"tweet_id": str, "parent_id": str}))
    df = pd.concat(dfs, ignore_index=True)
    df["text"] = df["text"].fillna("")

    # check each hashtag file
    rows = []
    for (topic, tag, kind), g in df.groupby(["topic", "hashtag", "type"], sort=False):
        text = g["text"]
        rows.append({
            "topic": topic,
            "hashtag": "#" + tag,
            "type": kind,
            "rows": len(g),
            "parents": g["parent_id"].nunique() if kind == "reply" else "",
            "dup_text_%": round(100 * text.str.strip().str.lower().duplicated().mean()),
            "short_<3w_%": round(100 * (text.str.split().str.len() < 3).mean()),
            "has_link_%": round(100 * text.str.contains(r"https?://", regex=True).mean()),
            "date_min": g["created_at"].min()[:10],
            "date_max": g["created_at"].max()[:10],
        })
    table = pd.DataFrame(rows)
    print("\nPER HASHTAG")
    print(table.to_string(index=False))

    # put everything in one file for the notebook (the type column says post/reply)
    # same tweet under 2 hashtags of the same topic (#bts + #kpop) -> keep once
    # same tweet in 2 different topics -> drop it, it doesn't belong to one topic
    before = len(df)
    df = df.drop_duplicates(subset=["topic", "type", "tweet_id"])
    n_topics = df.groupby("tweet_id")["topic"].transform("nunique")
    cross = int((n_topics > 1).sum())
    df = df[n_topics == 1]
    same_topic = before - len(df) - cross
    print(f"\nMerged: {before} rows -> {len(df)} "
          f"({same_topic} same-topic duplicates, {cross} rows in 2+ topics dropped)")

    counts = df.pivot_table(index="topic", columns="type", values="tweet_id",
                            aggfunc="count", fill_value=0)
    print("\nPER TOPIC")
    print(counts.to_string())

    df[COLUMNS].to_csv(out / "combined.csv", index=False, encoding="utf-8")
    table.to_csv(out / "summary_per_hashtag.csv", index=False, encoding="utf-8")

    # 20 random tweets per hashtag to check spam by hand in Excel
    parts = []
    for _, g in df.groupby(["hashtag", "type"]):
        parts.append(g.sample(min(len(g), 20), random_state=42))
    sample = pd.concat(parts)
    sample = sample[["topic", "hashtag", "type", "tweet_id", "text"]].copy()
    sample["is_spam_or_ad"] = ""
    sample.to_csv(out / "spam_check.csv", index=False, encoding="utf-8-sig")

    print(f"\nSaved {out / 'combined.csv'}, summary_per_hashtag.csv and spam_check.csv")


async def login(args):
    from twscrape import API

    username = os.environ.get("X_USERNAME")
    cookies = os.environ.get("X_COOKIES")
    if not username or not cookies:
        sys.exit("Set X_COOKIES and X_USERNAME in this terminal first.")

    args.db.parent.mkdir(parents=True, exist_ok=True)
    api = API(str(args.db))
    try:
        await api.pool.add_account_cookies(username, cookies)
    except ValueError as e:
        sys.exit(f"Bad X_COOKIES: {e}")

    print(f"Saved cookies for {username}.")
    print("Accounts:")
    for a in await api.pool.accounts_info():
        print(f"  {a['username']}: active={a['active']}")


def main():
    sys.stdout.reconfigure(errors="replace")  # emoji can crash the Windows terminal

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect")
    c.add_argument("--since", required=True)    # YYYY-MM-DD
    c.add_argument("--until", required=True)    # YYYY-MM-DD, not included
    c.add_argument("--out-dir", default="data/raw")
    c.add_argument("--type", choices=["post", "reply", "both"], default="both")
    c.add_argument("--topics", nargs="*", choices=list(TOPICS))
    c.add_argument("--posts-per-tag", type=int, default=105)   # 15 a day
    c.add_argument("--reply-posts", type=int, default=7)       # 1 parent post a day
    c.add_argument("--per-post", type=int, default=20)         # max replies per parent post
    # 10 not 20: in the pilot almost no pets post had 20 replies
    c.add_argument("--min-replies", type=int, default=10)
    c.add_argument("--wait", type=int, default=900)            # seconds to wait when rate-limited
    c.add_argument("--db", type=Path, default=DEFAULT_DB)
    c.add_argument("--dry-run", action="store_true")

    s = sub.add_parser("summary")
    s.add_argument("--out-dir", default="data/raw")

    lg = sub.add_parser("login")
    lg.add_argument("--db", type=Path, default=DEFAULT_DB)

    args = parser.parse_args()
    if args.cmd == "collect":
        asyncio.run(collect(args))
    elif args.cmd == "login":
        asyncio.run(login(args))
    else:
        summary(args)


if __name__ == "__main__":
    main()
