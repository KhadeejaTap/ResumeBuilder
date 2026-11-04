import pdfplumber
import json
from llm_client import ask
from job_scraper import clean_json_text

def extract_text(pdf_path):
	text = ""
	with pdfplumber.open(pdf_path) as pdf:
		for page in pdf.pages:
			text += page.extract_text() or ""
	return text

def parse_resume(pdf_path):
	raw_text = extract_text(pdf_path)

	prompt = f"""Extract structured candidate information from this resume as JSON only, no markdown, no explanation.
Required JSON schema:
{{
  "first_name": "First name",
  "last_name": "Last name",
  "email": "Email address",
  "phone": "Phone number",
  "location": "City, State",
  "address": {{
    "street": "Street address if found, else empty string",
    "city": "City",
    "state": "State or region",
    "postal_code": "Postal or zip code if found, else empty string",
    "country": "Country (default: United States)"
  }},
  "linkedin": "LinkedIn profile URL or handle",
  "github": "GitHub profile URL or handle",
  "degree_type": "e.g. Bachelor of Science",
  "major": "e.g. Computer Science",
  "education": [
    {{
      "institution": "University name",
      "degree": "Degree and major",
      "location": "Location",
      "dates": "Start – End dates",
      "details": ["Coursework or achievements"]
    }}
  ],
  "experience": [
    {{
      "title": "Job Title",
      "organization": "Company Name",
      "location": "Location",
      "dates": "Start – End dates",
      "bullets": ["Bullet 1", "Bullet 2"]
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "type": "Project Type or Tech Stack",
      "dates": "Dates",
      "bullets": ["Bullet 1", "Bullet 2"]
    }}
  ],
  "skills": {{
    "Languages": ["..."],
    "Software Development": ["..."],
    "Web": ["..."],
    "AI/ML": ["..."],
    "Developer Tools": ["..."]
  }},
  "languages_spoken": [
    {{
      "language": "English",
      "proficiency": "Native / Bilingual"
    }}
  ],
  "work_authorization": {{
    "us_authorized": true,
    "require_sponsorship": false
  }}
}}

Resume text:
{raw_text}
"""
	result, usage, model, finish_reason = ask(prompt)
	structured = clean_json_text(result)
	return structured

# parse fielsds
#

def main():
	data = parse_resume("Khadeeja_Tapkirwala.pdf")
	out_file = "data.json"
	with open(out_file, "w") as f:
		json.dump(data, f)
	print(data)

main()
