# How Toxic Is X (Twitter)? A Topic Comparison

A text analytics final project at KMUTT.

We collected posts and replies from X on 6 topics, measured how toxic they are, and compared the result with what our group expected.

**Our three questions**

1. Which topics are the most toxic? Are replies worse than posts?
2. What kind of toxicity is most common in each topic (insult, swearing, threat...)?
3. How accurate is each method (bad-word list, Detoxify, Twitter-RoBERTa)? We check this against our own hand labels.

```
 1. Choose topics  →  2. Test scrape  →  3. Real scrape  →  4. Clean  →  5. Analyse  →  6. Hand-label
    (group vote)        (small runs)       (collect_x.py)     (notebook)    (notebook)      (make_label_sample.py
                                                                                             + notebook)
```

---

## 1. How we chose the topics

```
 Ask X users  →  Group discussion  →  12 candidate topics  →  Vote alone  →  Pick 6 topics
```

**Ask X users.** First we asked three people who use X **often**, **sometimes** and **rarely** which topics they think are toxic on X. We asked people with different habits, because heavy users and light users see different parts of X.

| Person | Uses X | High | Mid | Low |
|---|---|---|---|---|
| Person 1 | Often | US politics, video game fandoms, artist fandoms | Sports (NBA, NFL, football) | none |
| Person 2 | Sometimes | US politics (Trump, Biden), artist fandoms (K-pop, T-pop) | Sports, games, movies/anime, tech | Travel, pets/animals |
| Person 3 | Rarely | School bullying | Games | Personal posts |

**Group discussion.** We talked about these answers together and made a list of 12 topics to vote on. Topics that came up more than once (politics, fandoms, sports, games) went on the list. We left some out:

| Left out | Why |
|---|---|
| School bullying | It is about toxicity by definition, so it would score high just because of the subject |
| Personal posts | Too broad, and there is no hashtag for it. Most personal posts are about everyday life, so we used everyday topics instead: travel, pets, food and nature |
| T-pop | Most tweets are in Thai, and our models only work in English |

So the calm topics in our list (travel, pets, food, nature) come from Person 2's Low answers and from Person 3's "personal posts".

The 12 topics for the vote: US Politics, Video Games, K-pop Fandoms, Western Music Fandoms, Sports, Movies & TV, Anime, Tech & AI, Travel, Pets & Animals, Food & Cooking, Nature & Photography.

**Vote.** Each of the 6 members rated the 12 topics alone as High, Mid or Low expected toxicity. For each topic we counted the **% agreement**: how many members chose the most common answer. It was between 67% and 100%.

**Discussion.** Then we talked together and picked 2 topics per level. We chose topics where everyone agreed (100%). Four Low topics tied, so we chose Pets and Food because they get more replies.

| Topic | Votes (H / M / L) | Agreement | Group level | Result |
|---|---|---|---|---|
| US Politics | 6 / 0 / 0 | 100% | High | **Selected** (High): everyone agreed |
| K-pop Fandoms | 6 / 0 / 0 | 100% | High | **Selected** (High): everyone agreed |
| Western Music Fandoms | 5 / 1 / 0 | 83% | High | Not everyone agreed, and K-pop already covers music fandoms |
| Video Games | 4 / 2 / 0 | 67% | High | The group was split between High and Mid |
| Sports | 2 / 4 / 0 | 67% | Mid | The group was split between High and Mid |
| Anime | 2 / 4 / 0 | 67% | Mid | The group was split between High and Mid |
| Movies & TV | 0 / 6 / 0 | 100% | Mid | **Selected** (Mid): everyone agreed |
| Tech & AI | 0 / 6 / 0 | 100% | Mid | **Selected** (Mid): everyone agreed |
| Pets & Animals | 0 / 0 / 6 | 100% | Low | **Selected** (Low): everyone agreed, and pet posts get replies |
| Food & Cooking | 0 / 0 / 6 | 100% | Low | **Selected** (Low): everyone agreed, and viral food posts get replies |
| Travel | 0 / 0 / 6 | 100% | Low | Tie at 100%, but fewer replies and many hotel/tour ads |
| Nature & Photography | 0 / 0 / 6 | 100% | Low | Tie at 100%, but people mostly like these posts and rarely reply, and many accounts are bots |

**Hashtags.** We picked 3 neutral hashtags per topic. We avoided hashtags about one person, company or news story (like `#musk` or `#nvidia`), because they pull in tweets about something else, for example Musk tweets would really be about politics.

| Topic | Hashtags |
|---|---|
| US Politics | #uspolitics #Republicans #Democrats |
| K-pop | #bts #blackpink #kpop |
| Movies | #movies #film #netflix |
| Tech | #AI #tech #iphone |
| Pets | #pets #catlovers #doglovers |
| Food | #recipe #cooking #foodie |

## 2. Test scrape

**First test (`test_twscrape.py`).** We checked that we can log in to X with `twscrape` and collect tweets for one hashtag.

**Small test run (first version of `collect_x.py`, data saved in `data/pilot/`).** Before the real run, we did a quick, small scrape with the first version of our code for 9–15 November: 50 posts per hashtag, and the replies under 1 post per hashtag (posts with 20+ replies). Then `collect_x.py summary` made a table for each hashtag (`summary_per_hashtag.csv`) with the number of tweets, the number of parent posts, the % of duplicate text, and the first and last date. Every hashtag returned posts, but the table showed three problems, so we improved the code (the current `collect_x.py`):

| Problem | Evidence in the small test run | What we changed | Result in the real run |
|---|---|---|---|
| Posts came only from the last few days | We asked for 9–15 Nov, but all 884 posts were from 13–15 Nov (514 from 15 Nov alone). X shows the newest tweets first, so the search never reached the older days | Search each day separately: 15 posts per day for 7 days | About 260 posts on every day from 9 to 15 Nov |
| Few pets posts had 20+ replies | #pets and #doglovers found no post with 20+ replies, so they got 0 replies. In the sample, 0 of 147 pets posts had 20+ replies | Need only 10+ replies (same rule for every topic) | All 3 pets hashtags have replies (68 in total) |
| All replies for a hashtag came from **one post** | Every hashtag had only 1 parent post. For #bts, 22 of 30 replies were the same fan message ("congratulations bts ... paved the way"), 70% duplicate text | Use **7 parent posts per hashtag** (one per day) and up to 20 replies under each | #bts replies come from 6 posts and only 11% are duplicate text |

**One more problem in the real run.** The first real run of pets (kept in `data/old_pets_v1/`) had 105 posts per hashtag, but only 90 different tweets: 15 were collected twice, and 9 November was missing. The reason is that X's `since:`/`until:` dates follow the account's time zone, not UTC, so the day windows overlapped. We switched to exact UTC times (`since_time:`/`until_time:`) and collected pets again. Now each pets hashtag has 101–103 different posts, 15 per day from 9 November.

**Still a limit.** Pets posts get few replies even with the 10+ rule: #doglovers has only 7 replies from 1 post. So the pets reply results are based on a small sample.

## 3. Real scrape

```powershell
python collect_x.py collect --since 2026-11-09 --until 2026-11-16
python collect_x.py summary --out-dir data/raw
```

- **Dates:** 9–15 November 2026, the same week for every topic.
- **Posts:** original tweets only (no retweets, no replies), 105 per hashtag.
- **Replies:** direct English replies under posts with 10+ replies.
- **Result:** 2,829 tweets (1,846 posts and 983 replies).

`summary` puts all posts and replies into one file, `data/raw/combined.csv`, so the notebook reads one table. The `type` column keeps posts and replies apart. A tweet that has two hashtags of the same topic (e.g. #bts and #kpop) is kept once. A tweet found in two different topics is removed, because it can't fairly count for either.

## 4. Clean (in the notebook)

| Step | Rule | Why |
|---|---|---|
| 1 | Remove tweets with a link **and** 3+ hashtags | These are ads and auto-posts, not people talking |
| 2 | Remove links and the @names at the start of replies | Only the message should be scored |
| 3 | Remove the same text repeated within a topic and type (posts or replies) | Copy-paste campaigns and bots |
| 4 | Remove texts under 3 words | Too short to judge ("lol") |

After cleaning, **1,594 tweets** were left. Most removed tweets were ad **posts** (pets posts went from 304 to 83). Almost all replies stayed.

## 5. Analyse (in the notebook)

We score every tweet with three methods and call it toxic if the score is 0.5 or more (for the word list: at least one bad word):

| Method | Idea |
|---|---|
| Bad-word list | Is any word from the [LDNOOBW](https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words) English list (403 words and phrases) in the tweet? (`resources/ldnoobw_en.txt`). A widely used GitHub list. We also tested two other lists ([badwordslist](https://code.google.com/archive/p/badwordslist/) and [google-profanity-words](https://github.com/coffee-and-fun/google-profanity-words)): they flagged more harmless words (e.g. "turkey breasts", "hell yeah") and still missed more than half of the toxic tweets, so we kept LDNOOBW |
| Detoxify (unbiased) | AI model trained on online comments. Gives a toxicity score and 5 types. We load its weights (`unitary/unbiased-toxic-roberta`) with `transformers` |
| Twitter-RoBERTa | AI model trained on tweets (`cardiffnlp/twitter-roberta-base-offensive`) |

**First look.** All three methods put US Politics first. For replies, Detoxify and RoBERTa give the same order (US Politics > K-pop > Pets > Movies > Food > Tech). The word list finds almost no bad words outside politics (0–2 replies per topic). Over all topics, replies and posts are about equally toxic (Detoxify: 7.7% of replies, 7.6% of posts).

**Our guess vs. the data.** For each method we rank the 6 topics by % toxic replies and call the top 2 High, the middle 2 Mid and the bottom 2 Low, the same 2/2/2 split as our vote. Detoxify and RoBERTa match our guess for 4 of 6 topics: Tech came out lower and Pets higher than we guessed (but Pets has only 53 replies). The word list matches only 1 of 6.

**Thresholds.** We also tried 0.2, 0.5 and 0.8 for both models. For replies, Detoxify gives 4/6 at all three. RoBERTa gives 4/6 only at 0.5, because its scores are spread out (450 tweets above 0.2, only 50 above 0.8). US Politics is the most toxic topic at every threshold for both models, so we keep the usual default of 0.5.

**A closer look.** The 15 highest-scoring tweets for each model are almost all US Politics personal attacks (14 of 15 for Detoxify, 13 of 15 for RoBERTa). Reading the top tweets per topic shows that most "toxic" tweets in calm topics are false alarms: friendly swearing ("Damn these look so good!"), double meanings ("tiny pussy cat") and violent words in a harmless context ("Slap the dog"). Pets' Mid level comes from 3 toxic replies, and only 1 of them is a real attack.

**Type of toxicity.** Insult is the most common type in the topics with enough toxic tweets: US Politics 75%, K-pop 78% and Movies 62%. Swearing (obscene) is second. Threats, identity attacks and sexual content are rare. Tech, Pets and Food have only 4–7 toxic tweets each, so their mix is not reliable.

**How accurate is each method? (hand labels)** We labelled a sample of 204 replies by hand. The sample has all 102 replies flagged by at least one method (for precision) and 17 random un-flagged replies per topic (for recall). Each un-flagged reply is weighted to stand for all un-flagged replies of its topic, so the scores are estimates for all 817 replies. Two members labelled every reply alone, without the topic or scores, and a third member decided the 21 disagreements. The two labellers agreed on 183 of 204 (90%, Cohen's kappa 0.76).

| Method | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|
| Word list | 0.88 | 0.29 | 0.43 | 0.933 |
| Detoxify | 0.79 | 0.69 | 0.74 | 0.956 |
| RoBERTa | 0.67 | 0.85 | 0.75 | 0.950 |

The two models are about equally good, but Detoxify is more careful and RoBERTa finds more. The word list is usually right when it finds a bad word but misses most toxic replies, because insults like *stupid* or *trash* are not swear words. Accuracy is misleading here because about 91% of replies are not toxic. 95% of replies flagged by all three methods are really toxic, but only 41% of those flagged by just one.

```powershell
pip install torch transformers nltk scikit-learn matplotlib pandas jupyter
```

Open `toxicity_analysis.ipynb` and choose **Run All**. The first run downloads the models, scores all tweets and finds the trigger words (the trigger words alone take about 8 minutes). The results are saved in `data/scored.csv` and `data/trigger_words.csv` and reused next time.

The figures are saved to `figures/` with the same numbers as in the report (`fig1_toxic_by_topic.png` = Figure 1, ..., `fig5_method_scores.png` = Figure 5). The appendix tables are the outputs of notebook section 7.

**Hand labelling.** `python make_label_sample.py` makes the sample in `data/labelling/`: `labeller_A.csv` and `labeller_B.csv` (no topic, no scores, shuffled), `key.csv` (scores and weights) and `INSTRUCTIONS.txt`. It never overwrites label files that already exist. After both labellers finish, the notebook (section 6.1) saves `disagreements.csv`. The third member fills in its `final` column, and section 6.2 then computes the scores.

---

## How to run the scraper

You need Python, `pip install twscrape pandas`, and an X account (use a spare one, because X can block accounts that scrape).

1. Log in to x.com in your browser. Copy `auth_token` and `ct0` from DevTools (Application > Cookies > `https://x.com`).
2. Save them (once per account):

   ```powershell
   $env:X_COOKIES = "auth_token=PASTE_HERE; ct0=PASTE_HERE"
   $env:X_USERNAME = "your_x_handle"
   python collect_x.py login
   ```

3. Check the searches without sending anything: add `--dry-run` to the collect command.
4. Run the collect and summary commands from section 3.

**Rate limits:** X only allows a certain number of searches every 15 minutes. The script waits by itself. If it stops, wait 15 minutes and run the same command again. Finished files are skipped. The full run took about 1–2 hours.

## Files

| File | What it is |
|---|---|
| `collect_x.py` | Scraper: collects posts and replies, then makes `combined.csv` |
| `toxicity_analysis.ipynb` | Cleaning, scoring, hand-label evaluation and all results |
| `make_label_sample.py` | Makes the 204-reply sample and the label sheets for hand labelling |
| `test_twscrape.py` | Our first scraping test (one hashtag) |
| `resources/ldnoobw_en.txt` | Bad-word list |
| `figures/` | Figures 1–5 of the report (same numbers) |
| `data/labelling/` | Label sheets, `key.csv` and the third member's `disagreements.csv` |
| `data/` | Tweets and scores. **Not committed to Git** |

## Important

- **Never put cookies in a file.** They give full access to the X account. Type them only in the terminal.
- **No usernames in the report or slides.** We don't save usernames or links.
- **Scraping breaks X's terms of use.** twscrape uses X's private API.

## Limitations

- One platform (X), English only, one week (just after the 2026 US midterm elections).
- Hashtag tweets may not represent everything people say about a topic.
- Posts come mostly from the last hours of each day, because X shows the newest first.
- Pets has few replies (53 after cleaning), so its result is less certain.
- K-pop uses the two biggest fandoms, which may argue more than smaller ones.
- The AI models were trained on other data, and they see a reply without the full conversation.
- Removing tweets shorter than 3 words may have removed some short toxic replies.
- The hand labels are our own judgement. Recall comes from only 17 un-flagged replies per topic. Just 1 of those 102 was labelled toxic, and it stands for about 7 replies, so recall would change noticeably if that one label changed.
