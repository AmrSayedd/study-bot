CREATE_COURSES = """
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_LECTURES = """
CREATE TABLE IF NOT EXISTS lectures (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id),
    title TEXT NOT NULL,
    summary TEXT,
    key_concepts TEXT,
    important_equations TEXT,
    common_misconceptions TEXT,
    compressed_knowledge TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_LECTURE_SOURCES = """
CREATE TABLE IF NOT EXISTS lecture_sources (
    id SERIAL PRIMARY KEY,
    lecture_id INTEGER NOT NULL REFERENCES lectures(id),
    filename TEXT NOT NULL,
    original_text TEXT,
    file_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_QUESTIONS = """
CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    lecture_id INTEGER NOT NULL REFERENCES lectures(id),
    question_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT,
    difficulty INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_REMINDERS = """
CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    course TEXT,
    lecture TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    next_review_at TIMESTAMP,
    interval_days DOUBLE PRECISION DEFAULT 1.0,
    repetitions INTEGER DEFAULT 0
)
"""

CREATE_PERFORMANCE = """
CREATE TABLE IF NOT EXISTS performance_tracking (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    question_id INTEGER REFERENCES questions(id),
    lecture_id INTEGER REFERENCES lectures(id),
    course_id INTEGER REFERENCES courses(id),
    topic TEXT,
    correct SMALLINT,
    confidence INTEGER,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_USER_PREFERENCES = """
CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    pref_key TEXT NOT NULL,
    pref_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, pref_key)
)
"""

CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    current_course_id INTEGER REFERENCES courses(id),
    current_lecture_id INTEGER REFERENCES lectures(id),
    revision_mode TEXT DEFAULT 'daily',
    history TEXT DEFAULT '[]',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_PERFORMANCE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_perf_user_topic ON performance_tracking(user_id, topic)
"""

CREATE_VOCABULARY = """
CREATE TABLE IF NOT EXISTS vocabulary (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    course_id INTEGER REFERENCES courses(id),
    lecture_id INTEGER REFERENCES lectures(id),
    word TEXT NOT NULL,
    meaning TEXT,
    example TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

ALL_TABLES = [
    CREATE_COURSES,
    CREATE_LECTURES,
    CREATE_LECTURE_SOURCES,
    CREATE_QUESTIONS,
    CREATE_REMINDERS,
    CREATE_PERFORMANCE,
    CREATE_USER_PREFERENCES,
    CREATE_SESSIONS,
    CREATE_VOCABULARY,
    CREATE_PERFORMANCE_INDEX,
]
