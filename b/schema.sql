PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS books (id TEXT PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS paragraphs (book_id TEXT NOT NULL, id TEXT NOT NULL, chapter INTEGER NOT NULL CHECK(chapter > 0), text TEXT NOT NULL, PRIMARY KEY(book_id,id), FOREIGN KEY(book_id) REFERENCES books(id));
CREATE TABLE IF NOT EXISTS chapters (book_id TEXT NOT NULL, number INTEGER NOT NULL CHECK(number > 0), title TEXT NOT NULL, PRIMARY KEY(book_id,number), FOREIGN KEY(book_id) REFERENCES books(id));
CREATE TABLE IF NOT EXISTS people (book_id TEXT NOT NULL, id TEXT NOT NULL, first_chapter INTEGER NOT NULL CHECK(first_chapter > 0), PRIMARY KEY(book_id,id), FOREIGN KEY(book_id) REFERENCES books(id));
CREATE TABLE IF NOT EXISTS names (id INTEGER PRIMARY KEY, book_id TEXT NOT NULL, person_id TEXT NOT NULL, name TEXT NOT NULL, known_chapter INTEGER NOT NULL CHECK(known_chapter > 0), paragraph_id TEXT NOT NULL, FOREIGN KEY(book_id,person_id) REFERENCES people(book_id,id), FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id));
CREATE TABLE IF NOT EXISTS name_identity_evidence (name_id INTEGER PRIMARY KEY, quote TEXT NOT NULL, FOREIGN KEY(name_id) REFERENCES names(id));
CREATE TABLE IF NOT EXISTS relations (id INTEGER PRIMARY KEY, book_id TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL, relation TEXT NOT NULL, directed INTEGER NOT NULL CHECK(directed IN (0,1)), action TEXT NOT NULL CHECK(action IN ('assert','end')), known_chapter INTEGER NOT NULL CHECK(known_chapter > 0), paragraph_id TEXT NOT NULL, event_id TEXT, story_order TEXT NOT NULL DEFAULT 'unknown', FOREIGN KEY(book_id,source_id) REFERENCES people(book_id,id), FOREIGN KEY(book_id,target_id) REFERENCES people(book_id,id), FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id));

CREATE TABLE IF NOT EXISTS relation_evidence (
 relation_id INTEGER PRIMARY KEY, quote TEXT NOT NULL, candidate_id TEXT,
 FOREIGN KEY(relation_id) REFERENCES relations(id), FOREIGN KEY(candidate_id) REFERENCES candidates(id)
);

CREATE TABLE IF NOT EXISTS candidates (id TEXT PRIMARY KEY, book_id TEXT NOT NULL, chapter INTEGER NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('person','relation')), payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected')), FOREIGN KEY(book_id) REFERENCES books(id));

CREATE TABLE IF NOT EXISTS candidate_review_actions (
 id TEXT PRIMARY KEY, book_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
 candidate_type TEXT NOT NULL CHECK(candidate_type IN ('candidate','fact')),
 action TEXT NOT NULL CHECK(action IN ('accept','reject','reopen')),
 known_chapter INTEGER NOT NULL CHECK(known_chapter>0), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS extraction_cache (book_id TEXT NOT NULL, chapter INTEGER NOT NULL, cache_key TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(book_id,chapter,cache_key), FOREIGN KEY(book_id) REFERENCES books(id));
CREATE TABLE IF NOT EXISTS person_merges (id TEXT PRIMARY KEY, book_id TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL, known_chapter INTEGER NOT NULL, paragraph_id TEXT NOT NULL, quote TEXT NOT NULL, FOREIGN KEY(book_id,source_id) REFERENCES people(book_id,id), FOREIGN KEY(book_id,target_id) REFERENCES people(book_id,id), FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id));

CREATE TABLE IF NOT EXISTS call_budget (id INTEGER PRIMARY KEY CHECK(id=1), max_calls INTEGER NOT NULL CHECK(max_calls>=0));
INSERT OR IGNORE INTO call_budget VALUES (1,0);
CREATE TABLE IF NOT EXISTS call_log (id TEXT PRIMARY KEY, book_id TEXT NOT NULL, chapter INTEGER NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL, usage TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS merge_corrections (merge_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(merge_id) REFERENCES person_merges(id));

-- 关系变化的故事时间约束：依据出现章节决定何时可用。
CREATE TABLE IF NOT EXISTS relation_order_constraints (
  id TEXT PRIMARY KEY, book_id TEXT NOT NULL, before_id INTEGER NOT NULL, after_id INTEGER NOT NULL,
  known_chapter INTEGER NOT NULL CHECK(known_chapter > 0), paragraph_id TEXT NOT NULL, quote TEXT NOT NULL,
  FOREIGN KEY(book_id) REFERENCES books(id), FOREIGN KEY(before_id) REFERENCES relations(id),
  FOREIGN KEY(after_id) REFERENCES relations(id), FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id),
  CHECK(before_id != after_id)
);

CREATE TABLE IF NOT EXISTS profile_candidates (
  id TEXT PRIMARY KEY, book_id TEXT NOT NULL, chapter INTEGER NOT NULL CHECK(chapter>0), payload TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected')),
  FOREIGN KEY(book_id) REFERENCES books(id)
);
CREATE TABLE IF NOT EXISTS profile_facts (
  id TEXT PRIMARY KEY, book_id TEXT NOT NULL, person_id TEXT NOT NULL, category TEXT NOT NULL, content TEXT NOT NULL,
  assertion_type TEXT NOT NULL CHECK(assertion_type IN ('explicit','claim','inference')),
  paragraph_id TEXT NOT NULL, quote TEXT NOT NULL, known_chapter INTEGER NOT NULL CHECK(known_chapter>0),
  candidate_id TEXT, FOREIGN KEY(book_id,person_id) REFERENCES people(book_id,id),
  FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id), FOREIGN KEY(candidate_id) REFERENCES profile_candidates(id)
);

CREATE TABLE IF NOT EXISTS record_corrections (
  id TEXT PRIMARY KEY, book_id TEXT NOT NULL, target_kind TEXT NOT NULL CHECK(target_kind IN ('relation','fact')),
  target_id TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('retract','restore')),
  paragraph_id TEXT NOT NULL, quote TEXT NOT NULL, reason TEXT NOT NULL, known_chapter INTEGER NOT NULL CHECK(known_chapter>0),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(book_id) REFERENCES books(id),
  FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id)
);
CREATE INDEX IF NOT EXISTS idx_record_corrections_view ON record_corrections(book_id,target_kind,target_id,known_chapter);

CREATE TABLE IF NOT EXISTS person_corrections (
 id TEXT PRIMARY KEY, book_id TEXT NOT NULL, person_id TEXT NOT NULL,
 action TEXT NOT NULL CHECK(action IN ('retract','restore')), paragraph_id TEXT NOT NULL,
 quote TEXT NOT NULL, reason TEXT NOT NULL, known_chapter INTEGER NOT NULL CHECK(known_chapter>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(book_id,person_id) REFERENCES people(book_id,id),
 FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id)
);
CREATE INDEX IF NOT EXISTS idx_person_corrections_view ON person_corrections(book_id,person_id,known_chapter);

-- 供事件时序模块交换数据的带依据记录；不要求共享数据库。
CREATE TABLE IF NOT EXISTS external_events (
 book_id TEXT NOT NULL, event_id TEXT NOT NULL, summary TEXT NOT NULL, source TEXT NOT NULL,
 paragraph_id TEXT NOT NULL, quote TEXT NOT NULL, known_chapter INTEGER NOT NULL CHECK(known_chapter>0),
 PRIMARY KEY(book_id,event_id), FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id)
);
CREATE TABLE IF NOT EXISTS external_event_orders (
 id TEXT PRIMARY KEY, book_id TEXT NOT NULL, before_event_id TEXT NOT NULL, after_event_id TEXT NOT NULL,
 paragraph_id TEXT NOT NULL, quote TEXT NOT NULL, known_chapter INTEGER NOT NULL CHECK(known_chapter>0), source TEXT NOT NULL,
 FOREIGN KEY(book_id,before_event_id) REFERENCES external_events(book_id,event_id),
 FOREIGN KEY(book_id,after_event_id) REFERENCES external_events(book_id,event_id),
 FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id), CHECK(before_event_id != after_event_id)
);
CREATE TABLE IF NOT EXISTS relation_event_links (
 id TEXT PRIMARY KEY, book_id TEXT NOT NULL, relation_id INTEGER NOT NULL, event_id TEXT NOT NULL,
 paragraph_id TEXT NOT NULL, quote TEXT NOT NULL, known_chapter INTEGER NOT NULL CHECK(known_chapter>0), source TEXT NOT NULL,
 FOREIGN KEY(relation_id) REFERENCES relations(id), FOREIGN KEY(book_id,event_id) REFERENCES external_events(book_id,event_id),
 FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id)
);

CREATE TABLE IF NOT EXISTS integration_corrections (
 id TEXT PRIMARY KEY, book_id TEXT NOT NULL, target_kind TEXT NOT NULL CHECK(target_kind IN ('event','event_order','event_link','relation_order')),
 target_id TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('retract','restore')), paragraph_id TEXT NOT NULL, quote TEXT NOT NULL, reason TEXT NOT NULL,
 known_chapter INTEGER NOT NULL CHECK(known_chapter>0), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(book_id,paragraph_id) REFERENCES paragraphs(book_id,id)
);
CREATE INDEX IF NOT EXISTS idx_integration_corrections ON integration_corrections(book_id,target_kind,target_id,known_chapter);

CREATE TABLE IF NOT EXISTS extraction_jobs (
 id TEXT PRIMARY KEY, book_id TEXT NOT NULL, start_chapter INTEGER NOT NULL, end_chapter INTEGER NOT NULL,
 next_chapter INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','cancelled','interrupted')),
 cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)), error TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(book_id) REFERENCES books(id), CHECK(start_chapter>0 AND end_chapter>=start_chapter)
);
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_book ON extraction_jobs(book_id,status);

CREATE TABLE IF NOT EXISTS reading_progress (
 book_id TEXT PRIMARY KEY, chapter INTEGER NOT NULL CHECK(chapter>0), updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(book_id) REFERENCES books(id)
);
