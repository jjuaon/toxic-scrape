# Make the sample of replies for hand labelling.
# sample = all replies flagged toxic by at least 1 method + 17 random not-flagged replies per topic
#
# Output in data/labelling/:
#   labeller_A.csv, labeller_B.csv  -> what the labellers see (no topic, no scores, shuffled)
#   key.csv                         -> sample_id with tweet_id, topic, scores and weight
#   INSTRUCTIONS.txt                -> labelling rules
#
# python make_label_sample.py               (writes to data/labelling)
# python make_label_sample.py other_folder  (writes somewhere else)
import sys
from pathlib import Path

import pandas as pd

SEED = 42
N_UNFLAGGED_PER_TOPIC = 17
DATA = Path(__file__).parent / "data"

args = [a for a in sys.argv[1:] if a != "--force"]
if len(args) > 0:
    OUT = Path(args[0])
else:
    OUT = DATA / "labelling"
OUT.mkdir(parents=True, exist_ok=True)

# don't overwrite sheets that may already have labels in them
for name in ["labeller_A.csv", "labeller_B.csv"]:
    if (OUT / name).exists() and "--force" not in sys.argv:
        sys.exit(f"{OUT / name} already exists, not overwriting the labels. "
                 "Use --force to replace it, or give another output folder.")

d = pd.read_csv(DATA / "scored.csv")
r = d[d["type"] == "reply"].copy()

r["flag_wordlist"] = r["bw_count"] > 0
r["flag_detoxify"] = r["detox_toxicity"] >= 0.5
r["flag_roberta"] = r["roberta_offensive"] >= 0.5
any_flag = r["flag_wordlist"] | r["flag_detoxify"] | r["flag_roberta"]
r["stratum"] = "unflagged"
r.loc[any_flag, "stratum"] = "flagged"

flagged = r[r["stratum"] == "flagged"].copy()
flagged["weight"] = 1.0

parts = []
for topic, g in r[r["stratum"] == "unflagged"].groupby("topic"):
    s = g.sample(n=N_UNFLAGGED_PER_TOPIC, random_state=SEED)
    # each sampled reply counts for this many not-flagged replies of its topic
    s["weight"] = len(g) / N_UNFLAGGED_PER_TOPIC
    parts.append(s)
unflagged = pd.concat(parts)

# shuffle so the flagged ones are not all together
sample = pd.concat([flagged, unflagged]).sample(frac=1, random_state=SEED).reset_index(drop=True)
sample.insert(0, "sample_id", [f"S{i + 1:03d}" for i in range(len(sample))])

key_cols = ["sample_id", "tweet_id", "topic", "stratum", "weight",
            "flag_wordlist", "flag_detoxify", "flag_roberta",
            "bw_words", "detox_toxicity", "roberta_offensive"]
sample[key_cols].to_csv(OUT / "key.csv", index=False, encoding="utf-8-sig")

sheet = pd.DataFrame()
sheet["sample_id"] = sample["sample_id"]
sheet["parent_text"] = sample["parent_clean"]
sheet["reply_text"] = sample["text_clean"]
sheet["label"] = ""   # 1 = toxic, 0 = not toxic
sheet["notes"] = ""
sheet.to_csv(OUT / "labeller_A.csv", index=False, encoding="utf-8-sig")
sheet.to_csv(OUT / "labeller_B.csv", index=False, encoding="utf-8-sig")

(OUT / "INSTRUCTIONS.txt").write_text(
    """HOW TO LABEL
============
Each labeller (A and B) fills in their OWN file. Do not look at the other file
or at key.csv until both are finished.

For each row, read the parent post for context, then judge ONLY the reply_text.

label = 1  (toxic)     a rude, disrespectful or unreasonable reply that is likely
                       to make someone leave the conversation
                       (insults, attacks on a person or group, threats, hateful
                       or harassing swearing)
label = 0  (not toxic) everything else, including friendly swearing
                       ("damn this looks so good"), jokes between fans, strong but
                       polite disagreement, and rude words used harmlessly

If you are unsure, pick the closer one and write a short reason in notes.
Leave no label empty.

After both are done, a third member decides every row where A and B disagree.
""",
    encoding="utf-8",
)

print(f"flagged: {len(flagged)}  unflagged sampled: {len(unflagged)}  total: {len(sample)}")
print(sample.groupby(["topic", "stratum"]).size().unstack(fill_value=0))
print(f"saved to {OUT}")
