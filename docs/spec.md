# Lead Radar: Project Specification

**Owner:** Gray Lining (graylining.com), a software agency
**Status:** Specification v1, source of truth for the build
**Audience:** Claude Code (implementer) and the owner (reviewer)

If anything in the codebase conflicts with this document, this document wins. If this document is silent or ambiguous, choose the simplest option that fits the principles in section 2, and record the decision in `docs/DECISIONS.md`.

---

## 1. Purpose

Find people on Reddit who are publicly asking for help that Gray Lining can provide, and alert the owner so he can reply personally.

The system is a **lead radar**, not a posting bot. It reads public Reddit pages, scores each new post for buying intent, and sends the best ones to Telegram with a link, a score, an explanation, and (optionally) an AI-written draft reply. A human decides whether to reply, and posts the reply himself.

### 1.1 What Gray Lining sells (this defines what a "lead" is)

A post is a good lead if the author plausibly needs one of these:

1. **Rescue of unfinished or broken software:** half-built MVPs, abandoned freelancer projects, AI-generated or "vibe-coded" apps (Lovable, Bolt, Cursor, Replit, v0) that work in demos but fail in production or won't scale.
2. **Legacy modernization:** inherited or unmaintainable codebases, rewrites, "nobody wants to touch it."
3. **AI products and integration:** LLM features, AI agents, AI pipelines, WhatsApp or chat concierges, AI proof-of-concept to production.
4. **Automation and workflows:** replacing manual business processes, data pipelines, internal tools.
5. **CTO-as-a-Service:** non-technical founders needing a technical cofounder, architecture, vendor evaluation, roadmap.
6. **Technical due diligence and security audits:** pre-funding or pre-acquisition code review.
7. **Embedded engineering:** agencies or teams needing extra senior engineers.
8. **Web and mobile app development, cloud and DevOps, Web3.**

The ideal lead is a **business owner or founder with budget** (they mention customers, revenue, funding, a team, or a deadline) describing a **concrete technical problem**. Hobbyists, students, job seekers, and people asking for free tutorials are not leads.

### 1.2 Non-goals (do not build these)

- No automated posting, commenting, voting, or direct messaging on Reddit. Ever.
- No use of the Reddit API, OAuth, or `.json` endpoints. Access is via browser automation of public pages only.
- No logging into Reddit with the owner's real account. Collection is logged-out.
- No collection of private user information. Store only what is publicly visible on the post page (see 8.4).
- No web dashboard in v1. Telegram plus a CLI is the full interface.
- No multi-user or SaaS features.

---

## 2. Design principles

1. **Human in the loop.** The system finds and ranks. The owner replies.
2. **Cheap first.** Rules are free and run on everything. Local ML runs only on what survives the rules. Paid cloud AI runs only on confirmed leads, only for drafting, and is optional.
3. **Light footprint on Reddit.** Few requests, human-like pacing, no parallel tabs. Prefer fetching one listing page over opening many posts.
4. **Explainable.** Every score must be traceable: which rules fired, which example was nearest, what the zero-shot labels said. Debuggability matters more than a fraction of accuracy.
5. **Editable without code.** Keywords, weights, subreddits, thresholds, example posts, and zero-shot labels live in YAML files.
6. **Gets better with use.** Thumbs up/down feedback becomes labeled training data.
7. **Runs on a normal Windows or Linux PC.** No GPU required. CPU-only inference must be fast enough.
8. **Fragile parts are isolated.** Reddit's markup will change. All selectors live in one file.

---

## 3. Architecture

```
Scheduler (loop with jitter)
   |
   v
[1 Collector]  Playwright -> listing pages -> candidate posts (title, link, time, author, subreddit, snippet)
   |
   v
[2 Dedupe]     SQLite: skip post IDs already seen
   |
   v
[3 Rules]      Title/snippet scoring, hard drops, keyword weights
   |   (drop if below fetch_threshold)
   v
[4 Body fetch] Open post page for candidates only, extract full text
   |
   v
[5 Rules v2]   Re-score with full text
   |   (drop if below ml_threshold)
   v
[6 ML scoring] Embeddings similarity -> optional zero-shot -> optional trained classifier
   |
   v
[7 Combine]    Final score + explanation
   |   (drop if below notify_threshold)
   v
[8 Notify]     Telegram message with buttons: Open | Draft reply | Good | Not a lead
   |
   v
[9 Feedback]   Button taps stored as labels -> used to train the classifier later
   |
   v
[10 Drafting]  (optional, on button tap) Claude API writes a helpful reply draft
```

Everything is stored in one SQLite file. The process is a single Python program: a main loop for collection and scoring, plus a Telegram polling task for button callbacks.

---

## 4. Tech stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Browser automation | `playwright` (Python), Chromium | Persistent profile directory, headless by default, headed via flag for debugging |
| Storage | SQLite via standard `sqlite3` | Single file `data/leadradar.db`, WAL mode |
| Config | YAML files + `pydantic` models for validation | Fail fast on invalid config |
| Local embeddings | `sentence-transformers`, default model `BAAI/bge-small-en-v1.5` (fallback `all-MiniLM-L6-v2`) | CPU, cached model |
| Zero-shot (optional stage) | `transformers` zero-shot pipeline, default `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` (fallback `facebook/bart-large-mnli`) | Only on posts that pass the rules |
| Classifier (later) | `scikit-learn` LogisticRegression on embeddings | Trained from feedback labels |
| Notifications | Telegram Bot API (plain HTTPS via `httpx`, long polling for callbacks) | No heavy bot framework required |
| Drafting (optional) | Anthropic API (`anthropic` SDK), model set in config | Off by default; key from env var |
| Logging | `logging` to rotating files plus console | |
| CLI | `typer` | |
| Tests | `pytest` | |
| Packaging | `pyproject.toml`, `uv` or `pip` | |

Do not add dependencies beyond this list without recording the reason in `docs/DECISIONS.md`.

---

## 5. Repository layout

```
lead-radar/
  SPEC.md                  # this file
  README.md                # short quickstart (generate from this spec)
  pyproject.toml
  .env.example             # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY (optional)
  config/
    config.yaml            # subreddits, pacing, thresholds, models, notifications
    rules.yaml             # phrase lists, weights, hard drops
    examples.yaml          # positive and negative example posts for embedding similarity
    zeroshot.yaml          # zero-shot labels and which count as "lead" labels
    draft_prompt.md        # system prompt for reply drafting
  src/leadradar/
    __init__.py
    cli.py                 # typer entrypoint
    config.py              # pydantic models, loaders
    db.py                  # schema, migrations, queries
    collector/
      browser.py           # playwright session management, pacing, block detection
      selectors.py         # ALL CSS selectors live here and nowhere else
      listing.py           # parse listing/search pages -> RawPost
      post.py              # parse single post page -> body text
    pipeline/
      dedupe.py
      rules.py             # rule engine
      embeddings.py        # similarity scorer
      zeroshot.py          # zero-shot scorer
      classifier.py        # train + predict from feedback
      combine.py           # final score + explanation
      run.py               # orchestrates one cycle
    notify/
      telegram.py          # send messages, handle callbacks
      format.py            # message formatting
    draft/
      drafter.py           # Claude API reply drafting
    models.py              # dataclasses: RawPost, Candidate, ScoreResult
  tests/
    fixtures/              # saved HTML pages, sample posts
    test_rules.py
    test_selectors.py
    test_combine.py
    test_dedupe.py
    golden_posts.yaml      # labeled posts used as a regression set
  data/                    # gitignored: db, browser profile, html snapshots, model cache
  docs/
    DECISIONS.md           # running log of implementation decisions
```

---

## 6. Configuration files

### 6.1 `config/config.yaml`

```yaml
collector:
  base: "https://old.reddit.com"       # verify in milestone 2; fall back to www.reddit.com if unavailable
  headless: true
  user_data_dir: "data/browser_profile"
  logged_in: false                      # must stay false
  min_delay_s: 6                        # min wait between page loads
  max_delay_s: 18                       # max wait between page loads
  max_pages_per_cycle: 25               # hard cap on page loads per cycle
  max_post_age_hours: 24
  cycle_interval_min: 20
  cycle_jitter_min: 6                   # random +/- added to interval
  quiet_hours: ["01:00", "06:00"]       # local time, no collection
  sources:
    - type: subreddit_new
      name: SaaS
    - type: subreddit_new
      name: startups
    - type: subreddit_new
      name: indiehackers
    - type: subreddit_new
      name: Entrepreneur
    - type: subreddit_new
      name: smallbusiness
    - type: subreddit_new
      name: vibecoding
    - type: subreddit_new
      name: ChatGPTCoding
    - type: subreddit_new
      name: lovable
    - type: subreddit_new
      name: nocode
    - type: subreddit_new
      name: forhire
    - type: search
      query: '"works locally" production'
      sort: new
    - type: search
      query: '"technical cofounder"'
      sort: new
  # The sources above are a starting set. Owner must check each subreddit's rules
  # and activity, and edit this list freely.

thresholds:
  fetch_body: 2          # rules score on title/snippet needed to open the post
  ml_stage: 4            # rules score on full text needed to enter ML scoring
  notify: 0.60           # final combined score (0..1) needed to notify

ml:
  mode: similarity       # similarity | similarity+zeroshot | classifier
  embedding_model: "BAAI/bge-small-en-v1.5"
  zeroshot_model: "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"
  max_chars: 2000        # truncate post text before ML
  classifier_min_labels: 100

weights:                 # used by combine.py; must sum to 1 within the active mode
  similarity:
    rules: 0.35
    embedding: 0.65
  similarity+zeroshot:
    rules: 0.25
    embedding: 0.40
    zeroshot: 0.35
  classifier:
    rules: 0.20
    classifier: 0.80

notify:
  telegram_enabled: true
  daily_digest_time: "21:00"
  max_notifications_per_day: 30     # safety valve

draft:
  enabled: false                    # opt-in
  model: "claude-sonnet-5-5"
  max_tokens: 500
  on_demand_only: true              # draft only when the owner taps "Draft reply"
```

### 6.2 `config/rules.yaml`

Each rule: a pattern (plain phrase or regex), a weight, optional scope (`title`, `body`, `any`). Matching is case-insensitive. Rule score is the sum of weights of matched rules, with each rule counted at most once per post.

```yaml
hard_drop:            # post is discarded immediately if any matches
  - pattern: '(?i)\bi am (a )?(student|looking for (a )?(job|work|internship))'
  - pattern: '(?i)^\[for hire\]'
  - pattern: '(?i)\b(homework|assignment|thesis)\b'
  - pattern: '(?i)\bhow (do|can) i become (a )?(developer|programmer)'
  - pattern: '(?i)\b(meme|shitpost)\b'

problem_phrases:       # weight +3
  weight: 3
  patterns:
    - "works locally"
    - "works on my machine"
    - "works in demo"
    - "doesn't scale"
    - "falls apart"
    - "keeps crashing"
    - "breaks in production"
    - "ai generated code"
    - "vibe coded"
    - "inherited codebase"
    - "inherited a codebase"
    - "developer left"
    - "developer disappeared"
    - "freelancer ghosted"
    - "freelancer abandoned"
    - "technical debt"
    - "legacy system"
    - "legacy code"
    - "need a technical cofounder"
    - "need a cto"
    - "non-technical founder"
    - "rewrite from scratch"
    - "mvp is stuck"

buying_phrases:        # weight +2
  weight: 2
  patterns:
    - "looking for a developer"
    - "looking for developers"
    - "need a developer"
    - "need someone to fix"
    - "hire a developer"
    - "hiring a developer"
    - "[hiring]"
    - "willing to pay"
    - "my budget"
    - "dev agency"
    - "software agency"
    - "outsource"
    - "recommend a developer"

business_signals:      # weight +2
  weight: 2
  patterns:
    - "my customers"
    - "our customers"
    - "our users"
    - "paying customers"
    - "revenue"
    - "mrr"
    - "seed round"
    - "raised funding"
    - "series a"
    - "due diligence"
    - "before launch"
    - "deadline"

service_keywords:      # weight +1
  weight: 1
  patterns:
    - "lovable"
    - "bolt.new"
    - "cursor"
    - "replit"
    - "supabase"
    - "django"
    - "fastapi"
    - "ai agent"
    - "llm"
    - "whatsapp bot"
    - "automation"
    - "workflow"
    - "integration"
    - "crm"
    - "smart contract"
    - "kubernetes"
    - "aws costs"

negative_phrases:      # weight -5
  weight: -5
  patterns:
    - "free tutorial"
    - "side project"
    - "just for fun"
    - "learning to code"
    - "which laptop"
    - "career advice"
    - "roast my"
    - "i will not promote"
    - "i'm available for hire"
    - "we build custom"          # competitors advertising
    - "dm me for services"

negation_guards:       # if matched, subtract 4 from the score (handles "NOT looking for a developer")
  - '(?i)\b(not|n''t|no longer) (looking|hiring|need)'
```

### 6.3 `config/examples.yaml`

Seed with at least 15 positive and 15 negative realistic example posts (short title plus 2-4 sentence body). Claude Code must write these during milestone 5, in the style of real Reddit posts, covering each service category in section 1.1. The owner will replace and extend them. Format:

```yaml
positive:
  - id: pos-001
    text: "My Lovable app worked great in the demo, but now that real users signed up it keeps timing out and I don't know where to start. We have about 40 paying customers and I'm worried we'll lose them. Looking for someone to take a look."
  # ...
negative:
  - id: neg-001
    text: "What laptop should I buy for learning web development? Budget is around $800."
  # ...
```

### 6.4 `config/zeroshot.yaml`

```yaml
hypothesis_template: "This post is from {}."
labels:
  - name: "someone with a business who needs help fixing, finishing, or rebuilding a software project"
    is_lead: true
  - name: "someone looking to hire a developer, agency, or technical cofounder"
    is_lead: true
  - name: "someone who wants to automate a business process or add AI to their product"
    is_lead: true
  - name: "someone asking for general advice or having a discussion"
    is_lead: false
  - name: "someone promoting their own product or service"
    is_lead: false
  - name: "someone looking for a job or learning to code"
    is_lead: false
```

Zero-shot score = sum of probabilities over `is_lead: true` labels (multi-label mode, normalized to 0..1).

---

## 7. Data model (SQLite)

```sql
CREATE TABLE posts (
  id TEXT PRIMARY KEY,            -- reddit fullname, e.g. t3_abc123
  subreddit TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT,                      -- null until fetched
  url TEXT NOT NULL,
  author TEXT,                    -- public username only
  created_utc INTEGER,            -- post time if parseable
  first_seen_utc INTEGER NOT NULL,
  source TEXT NOT NULL            -- which configured source produced it
);

CREATE TABLE scores (
  post_id TEXT NOT NULL REFERENCES posts(id),
  stage TEXT NOT NULL,            -- rules_title | rules_full | embedding | zeroshot | classifier | final
  score REAL NOT NULL,
  detail_json TEXT,               -- matched rules, nearest example id and similarity, zero-shot label probs
  created_utc INTEGER NOT NULL,
  PRIMARY KEY (post_id, stage)
);

CREATE TABLE notifications (
  post_id TEXT PRIMARY KEY REFERENCES posts(id),
  telegram_message_id INTEGER,
  sent_utc INTEGER NOT NULL
);

CREATE TABLE feedback (
  post_id TEXT PRIMARY KEY REFERENCES posts(id),
  label INTEGER NOT NULL,         -- 1 = good lead, 0 = not a lead
  created_utc INTEGER NOT NULL
);

CREATE TABLE outcomes (          -- manual tracking of what happened afterwards
  post_id TEXT PRIMARY KEY REFERENCES posts(id),
  replied INTEGER DEFAULT 0,
  got_response INTEGER DEFAULT 0,
  became_conversation INTEGER DEFAULT 0,
  became_client INTEGER DEFAULT 0,
  notes TEXT,
  updated_utc INTEGER
);

CREATE TABLE drafts (
  post_id TEXT PRIMARY KEY REFERENCES posts(id),
  draft_text TEXT NOT NULL,
  model TEXT,
  created_utc INTEGER NOT NULL
);

CREATE TABLE runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_utc INTEGER NOT NULL,
  finished_utc INTEGER,
  pages_loaded INTEGER,
  posts_seen INTEGER,
  posts_new INTEGER,
  posts_notified INTEGER,
  status TEXT,                    -- ok | partial | blocked | error
  error TEXT
);
```

Every post that enters the pipeline, including rejected ones, is stored with its stage scores. This is required for tuning (section 12).

---

## 8. Component specifications

### 8.1 Collector

**Goal:** return new candidate posts with minimal page loads.

- Use one Playwright persistent context, one page at a time. No concurrency.
- Wait `random.uniform(min_delay_s, max_delay_s)` between every navigation.
- Source types:
  - `subreddit_new`: load `{base}/r/{name}/new/`
  - `search`: load `{base}/search/?q={query}&sort=new` (and `restrict_sr` where a subreddit is specified)
- From each listing page, extract per post: id (fullname), subreddit, title, permalink URL, author, relative or absolute time, and any visible snippet. Listing pages on old Reddit show titles only, so body text requires opening the post.
- Stop paginating a source as soon as it reaches posts already in the database or older than `max_post_age_hours`.
- Respect `max_pages_per_cycle`. If the cap is hit, finish the cycle and log it.
- **Body fetch (stage 4):** open the post permalink only for candidates that passed the title-stage rules threshold. Extract the self-text body (truncate to 6,000 chars) and optionally the first 3 top-level comments from the author (not other users).
- **Block detection:** treat any of the following as a block: HTTP 429 or 403, a captcha or "verify you are human" page, a login wall on a page that should be public, an empty listing from a source that previously had posts. On block: stop the cycle immediately, mark the run `blocked`, apply exponential backoff (30 min, 1 h, 2 h, up to 6 h), and send one Telegram alert. Do not retry aggressively and do not attempt to bypass captchas.
- **Selectors:** keep every CSS or XPath selector in `collector/selectors.py`. Claude Code must verify real selectors against the live site during milestone 2 (the old Reddit layout uses `div.thing` with `data-fullname`, `a.title`, `time`, and `.usertext-body`, but treat this as a starting hypothesis, not fact).
- **Parse failure handling:** if a page loads but zero posts parse, save the raw HTML to `data/snapshots/` with a timestamp, log loudly, and alert once. This is the signal that selectors broke.
- Set a realistic desktop user agent and viewport. Do not install stealth or fingerprint-spoofing plugins.

### 8.2 Rules engine

- Load `rules.yaml`, compile all patterns once.
- `score_title(post)` runs rules against title plus any snippet. `score_full(post)` runs against title plus body.
- Output: total score, list of matched rule groups with the exact phrases, and a `dropped: bool` flag with the hard-drop reason if applicable.
- Scope: a post whose hard-drop rule matches is stored with `dropped` detail and never proceeds.
- Rules score is an integer sum, normalized for combination as `min(max(score, 0), 10) / 10`.

### 8.3 ML scoring

**Embeddings (default, always on in ML stages).**
- Embed all examples in `examples.yaml` once at startup (cache to disk, invalidate when the file or model changes).
- For each post, embed `title + "\n" + body[:max_chars]`.
- `pos_sim` = mean of top-3 cosine similarities to positive examples. `neg_sim` = max cosine similarity to negative examples.
- Embedding score = `clip((pos_sim - 0.5 * neg_sim) rescaled to 0..1)`. Define and document the exact rescaling empirically using `golden_posts.yaml` (section 12) so the score distribution separates the golden positives from negatives. Record the rescaling constants in `config.yaml`.
- Store the ids of the top-3 nearest positives and the nearest negative with their similarities in `detail_json`.

**Zero-shot (optional, `mode: similarity+zeroshot`).**
- Run only on posts that passed the rules and the embedding stage's lower bound. Truncate text to 512 tokens.
- Multi-label mode; score per section 6.4.
- Log per-label probabilities in `detail_json`.

**Classifier (`mode: classifier`, enabled automatically only when `feedback` has at least `classifier_min_labels` labels with at least 20 of each class).**
- Features: the same embedding vectors.
- Model: logistic regression with class weighting; keep a held-out split to report precision and recall.
- Command `leadradar train` retrains, evaluates, saves the model to `data/models/`, and prints metrics. Only swap the live mode if the new model beats embedding-similarity on the held-out set; otherwise keep the current mode and print why.

### 8.4 Combine

- Final score (0..1) = weighted sum per the active mode's `weights` in config.
- Notify if final score >= `thresholds.notify`.
- `detail_json` for the `final` stage must include a human-readable one-paragraph explanation, for example: "Matched rules: 'works locally' (+3), 'paying customers' (+2). Nearest positive example: pos-004 (0.81). Zero-shot top label: business needs help fixing software (0.77)."

**Privacy rule:** store only the post's public fields (title, body, URL, public username, subreddit, timestamps). Do not look up, scrape, or store anything about the author beyond the username shown on the post, and do not open author profile pages.

### 8.5 Telegram notifier

Message format (Markdown or HTML, whichever renders more reliably):

```
Lead (score 0.78) in r/SaaS
"My Lovable app keeps timing out under real users"

Why: matched 'paying customers', 'keeps crashing'; nearest example pos-004 (0.81)
Posted 14 min ago by u/example

[Open post] [Draft reply] [Good lead] [Not a lead]
```

- "Open post" is a URL button.
- "Draft reply" triggers drafting (section 8.6) and sends the draft as a follow-up message with a copy-friendly code block.
- "Good lead" and "Not a lead" write to the `feedback` table, edit the message to show the choice, and remove the buttons.
- Handle long polling in a background task with graceful shutdown. Only accept callbacks from the configured `TELEGRAM_CHAT_ID`.
- Enforce `max_notifications_per_day`. If exceeded, queue the rest into the daily digest.
- **Daily digest** at `daily_digest_time`: counts of posts seen, rules-dropped, ML-rejected, notified, plus the top 5 near-misses (final score between 0.45 and the notify threshold) with links, so the owner can spot missed leads.

### 8.6 Reply drafting (optional)

- Disabled unless `draft.enabled: true` and `ANTHROPIC_API_KEY` is set.
- Runs only on the "Draft reply" tap when `on_demand_only: true`.
- Input to the model: subreddit, post title, post body (truncated), and the system prompt in `config/draft_prompt.md`.
- `draft_prompt.md` must instruct the model to:
  - Write 80-150 words in plain, conversational English, in the first person, as a senior engineer who works at a software agency.
  - Start by restating and diagnosing the person's specific problem, with 1-3 concrete, technically sound observations or next steps they can act on immediately.
  - Not pitch, not include any link, and not use marketing language, bullet-pointed offers, or emojis in the first reply.
  - Disclose affiliation in one short, natural sentence (for example: "I run a small dev agency, so I've seen this a lot") only if the subreddit allows it; otherwise omit.
  - End with an open, low-pressure line such as offering to look at it further, without mentioning pricing.
  - Never invent facts about the poster's stack. If key details are missing, ask one clarifying question instead.
  - Never claim results, clients, or case studies that are not given in the prompt.
- Save every draft in `drafts`. The drafter must never post anything anywhere.

---

## 9. CLI

```
leadradar init-db                 # create the database and folders
leadradar run                     # long-running: collection loop + Telegram polling
leadradar run-once [--dry-run]    # one cycle; --dry-run prints results, sends nothing
leadradar replay [--since 7d]     # re-score stored posts offline (after editing rules or examples)
leadradar explain POST_ID         # print every stage score and explanation for a post
leadradar train                   # train classifier from feedback
leadradar stats                   # funnel counts, precision from feedback, top rules by hit rate
leadradar eval                    # score golden_posts.yaml and print precision/recall at current thresholds
leadradar snapshot-test           # run parsers against tests/fixtures HTML
leadradar export --csv PATH       # export posts, scores, feedback, outcomes
leadradar outcome POST_ID --replied --response --conversation --client   # manual outcome tracking
```

`replay` must not hit the network. It only reads from SQLite and re-runs scoring.

---

## 10. Scheduling and runtime behaviour

- `leadradar run` loops: do a cycle, sleep `cycle_interval_min` plus or minus random jitter, repeat.
- Skip cycles during `quiet_hours`.
- A cycle must be crash-safe: write results per post as they complete, and record the run in `runs` even on failure.
- Single-instance lock (lock file) so two copies cannot run.
- Graceful shutdown on Ctrl+C or SIGTERM: finish the current page, close the browser, commit the database.
- Provide a documented way to run at startup (Windows Task Scheduler entry or a systemd unit) in the README. Do not require it.

---

## 11. Security, compliance, and ethics

- Secrets only in `.env`. Never commit `.env`, `data/`, or the browser profile. Provide `.gitignore`.
- Automating Reddit pages without permission may conflict with Reddit's terms, and the access rules have been changing. The owner accepts this risk. The design reduces it by being read-only, logged-out, low-volume, and slow, and Claude Code must not add any feature that increases the footprint (concurrency, aggressive polling, stealth, captcha bypass, account creation).
- Replies are posted manually by the owner, using an account with real history, following each subreddit's rules on self-promotion, and disclosing affiliation where appropriate.
- No direct messages to Reddit users. If the owner later wants outbound DM outreach, it is a separate decision and out of scope.

---

## 12. Testing and tuning

1. **Unit tests** for the rules engine (matches, weights, hard drops, negation guards), dedupe, combine, and config validation.
2. **Fixture tests:** save real listing and post HTML pages in `tests/fixtures/` during milestone 2 and test the parsers against them, so selector breakage is caught without hitting Reddit.
3. **Golden set:** `tests/golden_posts.yaml` containing at least 40 labeled sample posts (20 leads, 20 non-leads, including tricky cases: negation, sarcasm, hobbyists describing real problems, agencies advertising). `leadradar eval` prints precision and recall at the current thresholds. Target on the golden set: precision >= 0.7 and recall >= 0.7 for the `similarity` mode.
4. **Near-miss review:** the daily digest lists near-misses. The owner marks any that were actually leads, and those become new entries in `examples.yaml` or labels in `feedback`.
5. Keep rejected posts and their scores (do not delete them), because the weekly tuning routine is: run `stats`, look at rules with high hit rate but low feedback precision, and edit `rules.yaml`.

---

## 13. Milestones (build in this order, stop and report after each)

1. **Skeleton:** repo layout, `pyproject.toml`, config loading and validation, `init-db`, logging, `.env.example`, `.gitignore`, README stub.
2. **Collector spike:** verify whether `old.reddit.com` listings are reachable logged-out, build listing and post parsers with fixtures and tests, pacing, block detection, snapshot-on-failure. Record the findings (which base URL works, what selectors exist) in `docs/DECISIONS.md`. **Do not proceed until the owner confirms the collector works on real pages.**
3. **Dedupe, rules engine, `replay`, `explain`**, and the unit tests. Seed `rules.yaml` as in section 6.2.
4. **Telegram notifier** with buttons and the feedback table; `run-once --dry-run` and live `run-once`.
5. **Embeddings stage** and `examples.yaml` seeding; build `golden_posts.yaml` and `eval`; calibrate the rescaling constants.
6. **Full loop:** `run` with scheduler, quiet hours, backoff, single-instance lock, daily digest, `stats`.
7. **Zero-shot stage** (behind `ml.mode`), with logged per-label probabilities.
8. **Classifier training** (`train`), including the automatic readiness check and comparison against the current mode.
9. **Drafting** with on-demand button, `draft_prompt.md`, and the `drafts` table.
10. **Polish:** README with Windows and Linux run instructions, startup scheduling instructions, `export`, `outcome`.

---

## 14. Acceptance criteria (v1 is done when)

- `leadradar run` runs unattended for 72 hours on the owner's PC without crashing, with at most the configured request volume per day.
- A block or captcha stops collection, backs off, and sends exactly one alert.
- A selector breakage produces an HTML snapshot and a single alert, not silent failure.
- Every notification carries an explanation that names the rules matched and the nearest example.
- Editing `rules.yaml`, `examples.yaml`, or `zeroshot.yaml` and running `replay` changes scores without touching code or the network.
- Thumbs up/down taps are stored and `train` can use them once enough labels exist.
- No code path posts, comments, votes, or sends messages to Reddit.
- `leadradar eval` meets the golden-set targets in section 12.
- Total cloud AI spend with drafting enabled stays under a few dollars per month at expected volume.

---

## 15. Decisions pending from the owner

Claude Code should pick the stated default and continue unless told otherwise, logging each choice in `docs/DECISIONS.md`.

| Decision | Default |
|---|---|
| Notification channel | Telegram (Slack or email can be added later behind the same interface) |
| Operating system for the first deployment | Windows 11 (keep paths cross-platform) |
| Subreddit list | The starter list in section 6.1 |
| Whether drafting is enabled at launch | No |
| Whether to run zero-shot from day one | No: start with `similarity`, add zero-shot at milestone 7 |
| Quiet hours | 01:00-06:00 local time |

---

## 16. Reference: reply and positioning notes for the owner

These are not code requirements. They are context for the drafting prompt and the owner's manual replies.

- Gray Lining's strongest proof points are its case studies: reviving a failing crypto trading automation platform, an AI WhatsApp concierge for a real-estate brokerage, and taking an AI-generated CRM to production readiness. Use them only in follow-up replies, only when relevant, never in a first reply.
- The no-cost system audit is the natural, low-pressure offer once a person responds.
- First replies should be useful on their own even if the person never answers.
