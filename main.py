from doctest import run_docstring_examples

from sentence_transformers import SentenceTransformer
import json
import argparse
import requests
from bs4 import BeautifulSoup
import trafilatura
from openrouter import OpenRouter
import os
from dotenv import load_dotenv
import re
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODEL = "openrouter/free"

client = OpenRouter(api_key = OPENROUTER_API_KEY)

END_MARKERS = [
    "about us",
    "about company",
    "about databricks",
    "benefits",
    "our commitment",
    "equal opportunity",
    "privacy policy",
    "base hourly pay"
]
SUBSECTIONS = {
    "experience": ["role", "responsibilities"],
    "leadership": ["role", "responsibilities"],
    "projects": ["technologies", "responsibilities"]
}
MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

#get job desc
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="job desc")

# remove unneeded text to make it easier for sentence transformers
def trim_job_text(text): # called in extract funct
    text = text.lower()

    for marker in END_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            return text[:idx]

    return text

def extract_main_content(html_content): # uses trafilatura to extract main text and trims
    main_text = trafilatura.extract(html_content)

    if main_text is None:
        raise ValueError("Could not extract main content.")
    main_text = trim_job_text(main_text)
    return main_text

def remove_words(text, words):
	pattern = r"\b(" + "|".join(words) + r")\b"
	return re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

def embed_main_content(main_text): # to be tested
	main_text = remove_words(main_text, ["intern", "internship", "interns", "interning", "student"])
	return MODEL.encode(main_text)

def embed_exp(json_file, section_heading): # eg (exp.json, projects)
	with open(json_file, "r") as file:
		resume = json.load(file)
	if not resume:
		raise Exception("resume input wrong or resume is empty (xp bar is low)")

	section_content = resume[section_heading] # section content is
	res = ""
	fields = SUBSECTIONS[section_heading]
	for entry in section_content: # ie for each role or project
		entry_text = "" # feed this to transfomer
		for field in fields: # eg role or project title , responsibilities
			value = entry[field]
			if isinstance(value, list):
				if field == "role": # roles can go by multiple titles
					value = ", ".join(value)
				else:
					value = "\n".join(value)
			entry_text += f"{field}: {value}\n"
		if entry.get("embedding"):
			continue
		entry_text = remove_words(entry_text, ["intern", "internship", "interns", "interning", "student"])
		embedding = MODEL.encode(entry_text).tolist()
		entry["embedding"] = embedding

	with open(json_file, "w") as file:
		json.dump(resume, file, indent = 4) # use sql later for more flexible
	# so embedding is rly long , maybe add to diff json?

def get_similarity_scores(exp_json, job_embedding): # returns similarity scores dict, testing needed.
	similarity_scores = {} # dict for exp subsection + id : score
	for section in SUBSECTIONS:
		embed_exp(exp_json, section)

	with open(exp_json, "r") as file:
		resume = json.load(file)

	for section in SUBSECTIONS:
		for entry in resume[section]:
			entry_id = entry["id"]
			entry_embedding = entry.get("embedding")
			if entry_embedding is None:
				print(f"No embedding found for {section} {entry_id}. Skipping.")
				continue
			score = MODEL.similarity(job_embedding, entry_embedding)
			similarity_scores[(section, entry_id)] = score.item()

	return similarity_scores #need to test the scores, return top 2-3 experiences and set threshold

"""def extract_skills_trafilatura(main_text):
	desc_text = main_text.lower()
	with open("skills.json", "r") as file:
		skills = json.load(file)

    matched_skills = []

    for skill in skills:
        if skill.lower() in desc_text:
            matched_skills.append(skill)


    return matched_skills"""
def print_scores(sorted_scores, exp_json):
	with open(exp_json, "r") as file:
		resume = json.load(file)
	x = 0
	for (section, entry_id), score in sorted_scores:
		entry = resume[section][entry_id]
		if section == "projects":
			role = entry.get("name", "N/A")
			label = "Project Name"
		else:
			role = entry.get("role", "N/A")
			label = "Role"
		if isinstance(role, list):
			role = ", ".join(role)

		if entry:
			print(f"Rank: {x}, Section: {section}, ID: {entry_id}, Score: {score:.4f}, {label}: {role}")
		else:
			print(f"Rank: {x}, Section: {section}, ID: {entry_id}, Score: {score:.4f}, Entry not found.")
		x+=1

def test_similarity_scores(resume_json, html_content):
	main_text = extract_main_content(html_content)
	print("job desc: ", main_text)
	job_embedding = MODEL.encode(main_text)
	sorted_scores = sorted(get_similarity_scores(resume_json, job_embedding).items(), key=lambda x: x[1], reverse=True)

	print("similarity scores:", print_scores(sorted_scores, resume_json))
	# user input
	user_in = input("Enter the ranks of the highlighted experiences (seperated by spaces): ")
	ranks = list(map(int, user_in.split()))

	# pass input and sorted similarity scores to ai_writer
	ai_writer(resume_json, ranks, sorted_scores)

def list_to_text(val):
	if isinstance(val, list):
		return "\n".join(val)
	return val

def ai_prompt(entry_info):
	response = requests.post(
		url = "https://openrouter.ai/api/v1/chat/completions",
		headers = {
			"Authorization": f"Bearer {OPENROUTER_API_KEY}",
			"Content-Type": "application/json",
		},
		# finish later FIXME losingmymind
	)
	return entry_desc

def ai_writer(json_file, chosen_indices, sorted_scores): # where similarity scores is a dict. call this after get similarity score
	#test on first item
	with open(json_file, "r") as file:
		resume = json.load(file)

	# ai writer needs to find chosen entries. then take role name and responsibilities and write using that.
	for c in chosen_indices:
		section = sorted_scores[c][0][0]
		id = sorted_scores[c][0][1]
		entry = resume[section][id]
		if section == "projects":
			label = "Project name"
		elif section == "experience":
			label = "Job title"
		else:
			label = "Leadership role"
		role = list_to_text(entry.get("role", entry.get("name", "")))
		responsibilities = list_to_text(entry.get("responsibilities", ""))
		entry_info = "" # what we pass to llm
		entry_info += f"{label}: {role}\nResponsibilities: {responsibilities}"
		# feed it to ai writer
		entry_desc = ai_prompt(entry_info)
		print(entry_info)

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

	test_similarity_scores("exp.json", html_content)
	# next use llm to write the resume
	# make extension


main()
