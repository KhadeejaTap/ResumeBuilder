import os
import requests
from dotenv import load_dotenv
from db import log_call, init_db

init_db()
load_dotenv()
def ask(prompt, model = "openrouter/auto"):
	resp = requests.post(
		url="https://openrouter.ai/api/v1/chat/completions",
		headers={
			"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
			"Content-Type" : "application/json",
		},
		json = {
			"model" : model,
			"messages" : [{"role": "user", "content": prompt}],
		},
	)
	resp.raise_for_status() # flag errors early
	data = resp.json()

	content = data['choices'][0]['message']['content']
	usage = data['usage']
	model_used = data['model']
	finish_reason = data['choices'][0]['finish_reason']

	log_call(model_used, prompt, content, usage, finish_reason)

	return content, usage, model_used, finish_reason

def main():
	print(ask("say hi in one sentence"))

#main()
