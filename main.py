from sentence_transformers import SentenceTransformer
import json
import argparse
import requests
from bs4 import BeautifulSoup
#get job desc
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="job desc")

def extract_skills(response):
	desc_soup = BeautifulSoup(response.text, "html.parser")
	desc_text = desc_soup.get_text(separator=" ", strip=True).lower()
	with open("skills.json", "r") as file:
		skills = json.load(file)
	matched_skills = []
	for skill in skills:
	    if skill.lower() in desc_text:
	        matched_skills.append(skill)
	return matched_skills

def main():
	# get and try url
	args = parser.parse_args()
	job_url = args.url
	try:
		response = requests.get(job_url, timeout=10)
		response.raise_for_status()
		html_content = response.text
		print(f"Got the response from {job_url}")
	except requests.exceptions.RequestException as e:
		print(f"Error: {e}")
	matched_skills = extract_skills(response)
	print(matched_skills) # prints ur skills that matched

main()
