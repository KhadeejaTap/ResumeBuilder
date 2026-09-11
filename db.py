import sqlite3 # built in library
import datetime

DB_PATH = "llm_logs.db"

def init_db():
	conn=sqlite3.connect(DB_PATH) # open a connection
	conn.execute("""
		CREATE TABLE IF NOT EXISTS llm_calls (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			timestamp TEXT,
			model TEXT,
			prompt TEXT,
			response TEXT,
			prompt_tokens INTEGER,
			completion_tokens INTEGER,
			total_tokens INTEGER,
			finish_reason TEXT
		)
	""")
	conn.commit() #save change
	conn.close()

def log_call(model, prompt, response, usage, finish_reason):
	conn = sqlite3.connect(DB_PATH)
	conn.execute("""
		INSERT INTO llm_calls (timestamp, model, prompt, response, prompt_tokens, completion_tokens, total_tokens, finish_reason)
		VALUES (?, ?, ?, ?, ? ,? ,?,?)
	""",
		(
			datetime.datetime.now().isoformat(),
			model,
			prompt,
			response,
			usage["prompt_tokens"],
			usage["completion_tokens"],
			usage["total_tokens"],
			finish_reason,
		)
	)
	conn.commit()
	conn.close()
