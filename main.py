from sentence_transformers import SentenceTransformer
import json
import argparse
import requests
from bs4 import BeautifulSoup
import trafilatura
#get job desc
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="job desc")

END_MARKERS = [
    "about us",
    "about company",
    "about databricks",
    "benefits",
    "our commitment",
    "equal opportunity",
    "privacy policy"
]
SUBSECTIONS = {
    "experience": ["role", "responsibilities"],
    "leadership": ["role", "responsibilities"],
    "projects": ["technologies", "responsibilities"]
}
MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
# remove unneeded text to make it easier for sentence transformers
def trim_job_text(text):
    text = text.lower()

    for marker in END_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            return text[:idx]

    return text

def extract_main_content(html_content):
    main_text = trafilatura.extract(html_content)

    if main_text is None:
        raise ValueError("Could not extract main content.")
    main_text = trim_job_text(main_text)
    return main_text

#match skills from desc and json
def extract_skills_trafilatura(main_text):
    desc_text = main_text.lower()

    with open("skills.json", "r") as file:
        skills = json.load(file)

    matched_skills = []

    for skill in skills:
        if skill.lower() in desc_text:
            matched_skills.append(skill)

    return matched_skills

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
		embedding = MODEL.encode(entry_text).tolist()
		entry["embedding"] = embedding
	with open(json_file, "w") as file:
		json.dump(resume, file, indent = 4) # use sql later for more flexible
	# so embedding is rly long , maybe add to diff json?
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

	#main_text = extract_main_content(html_content)
	#skill_matches = extract_skills_trafilatura(main_text)
	#print(skill_matches)
	#print(main_text)
	print(embed_exp("exp.json", "experience"))
	# next -  update res funct to recompute embeddings, err handling to ensure embeddings exist for every entry
	# get 1 embedding per post and get similarity score / compare with work exp embeddings
	# return based on threshold of similarity score or top x . this decides what to pass into the llm
main()
