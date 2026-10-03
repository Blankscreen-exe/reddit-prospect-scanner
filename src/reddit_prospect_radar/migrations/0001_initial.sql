-- Initial schema (spec section 7).
-- Every post that enters the pipeline is stored, including rejected ones, for tuning.

CREATE TABLE posts (
  id TEXT PRIMARY KEY CHECK (id GLOB 't3_?*'),  -- reddit fullname, e.g. t3_abc123
  subreddit TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT,                                    -- null until fetched
  url TEXT NOT NULL,
  author TEXT,                                  -- public username only
  created_utc INTEGER,                          -- post time if parseable
  first_seen_utc INTEGER NOT NULL,
  source TEXT NOT NULL                          -- key of the configured source that produced it
) STRICT;

CREATE INDEX idx_posts_first_seen_utc ON posts (first_seen_utc);

CREATE TABLE scores (
  post_id TEXT NOT NULL REFERENCES posts (id),
  stage TEXT NOT NULL CHECK (
    stage IN ('rules_title', 'rules_full', 'embedding', 'zeroshot', 'classifier', 'final')
  ),
  score REAL NOT NULL,
  detail_json TEXT,                             -- matched rules, nearest examples, label probs
  created_utc INTEGER NOT NULL,
  PRIMARY KEY (post_id, stage)
) STRICT;

CREATE INDEX idx_scores_stage ON scores (stage);

CREATE TABLE notifications (
  post_id TEXT PRIMARY KEY REFERENCES posts (id),
  telegram_message_id INTEGER,
  sent_utc INTEGER NOT NULL
) STRICT;

CREATE TABLE feedback (
  post_id TEXT PRIMARY KEY REFERENCES posts (id),
  label INTEGER NOT NULL CHECK (label IN (0, 1)),  -- 1 = good lead, 0 = not a lead
  created_utc INTEGER NOT NULL
) STRICT;

CREATE TABLE outcomes (                         -- manual tracking of what happened afterwards
  post_id TEXT PRIMARY KEY REFERENCES posts (id),
  replied INTEGER NOT NULL DEFAULT 0 CHECK (replied IN (0, 1)),
  got_response INTEGER NOT NULL DEFAULT 0 CHECK (got_response IN (0, 1)),
  became_conversation INTEGER NOT NULL DEFAULT 0 CHECK (became_conversation IN (0, 1)),
  became_client INTEGER NOT NULL DEFAULT 0 CHECK (became_client IN (0, 1)),
  notes TEXT,
  updated_utc INTEGER
) STRICT;

CREATE TABLE drafts (
  post_id TEXT PRIMARY KEY REFERENCES posts (id),
  draft_text TEXT NOT NULL,
  model TEXT,
  created_utc INTEGER NOT NULL
) STRICT;

CREATE TABLE runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_utc INTEGER NOT NULL,
  finished_utc INTEGER,
  pages_loaded INTEGER,
  posts_seen INTEGER,
  posts_new INTEGER,
  posts_notified INTEGER,
  status TEXT CHECK (status IN ('ok', 'partial', 'blocked', 'error')),  -- null while running
  error TEXT
) STRICT;
