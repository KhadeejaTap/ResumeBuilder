import os
import requests
from dotenv import load_dotenv
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
	return resp.json()["choices"][0]["message"]["content"]

def main():
	print(ask("say hi in one sentence"))

main()
