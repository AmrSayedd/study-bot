CREATE_COURSES = """
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_LECTURES = """
CREATE TABLE IF NOT EXISTS lectures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    key_concepts TEXT,
    important_equations TEXT,
    common_misconceptions TEXT,
    compressed_knowledge TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id)
)
"""

CREATE_LECTURE_SOURCES = """
CREATE TABLE IF NOT EXISTS lecture_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lecture_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_text TEXT,
    file_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lecture_id) REFERENCES lectures(id)
)
"""

CREATE_QUESTIONS = """
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lecture_id INTEGER NOT NULL,
    question_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT,
    difficulty INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lecture_id) REFERENCES lectures(id)
)
"""

CREATE_REMINDERS = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    course TEXT,
    lecture TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    next_review_at TIMESTAMP,
    interval_days REAL DEFAULT 1.0,
    repetitions INTEGER DEFAULT 0
)
"""

CREATE_PERFORMANCE = """
CREATE TABLE IF NOT EXISTS performance_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER,
    lecture_id INTEGER,
    course_id INTEGER,
    topic TEXT,
    correct BOOLEAN,
    confidence INTEGER,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id),
    FOREIGN KEY (lecture_id) REFERENCES lectures(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
)
"""

CREATE_USER_PREFERENCES = """
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    pref_key TEXT NOT NULL,
    pref_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, pref_key)
)
"""

CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    current_course_id INTEGER,
    current_lecture_id INTEGER,
    revision_mode TEXT DEFAULT 'daily',
    history TEXT DEFAULT '[]',
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (current_course_id) REFERENCES courses(id),
    FOREIGN KEY (current_lecture_id) REFERENCES lectures(id)
)
"""

CREATE_VOCABULARY = """
CREATE TABLE IF NOT EXISTS vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id INTEGER,
    lecture_id INTEGER,
    word TEXT NOT NULL,
    meaning TEXT,
    example TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (lecture_id) REFERENCES lectures(id)
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
]
