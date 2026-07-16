from sentence_transformers import SentenceTransformer
import json
import argparse
import requests
#get job desc
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="job desc")
#with open("skill.json", "r") as file:
#	SKILLS = json.load(file)

def main():
	args = parser.parse_args()
	job_url = args.url
	print(job_url)
	html_content = requests.get(job_url)
	print(html_content)

main()
