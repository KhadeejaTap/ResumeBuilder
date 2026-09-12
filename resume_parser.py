import pdfplumber
import json
from llm_client import ask

def extract_text(pdf_path):
	text = ""
	with pdfplumber.open(pdf_path) as pdf:
		for page in pdf.pages:
			text += page.extract_text() or ""
	return text

def parse_resume(pdf_path):
	raw_text = extract_text(pdf_path)

	prompt = f""""Extract structures info from this resume as JSON only, no markdown, no explanation. Fields: name, email, phone, education (list), experience (list), projects (list), skills (list).
	Resume text: {raw_text}
	"""
	result, usage, model, finish_reason = ask(prompt)
	structured = json.loads(result)
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
