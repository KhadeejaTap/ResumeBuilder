import os
import re
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from job_scraper import structure_job_with_llm, process_job
from tailor import tailor_resume, compile_pdf

app = FastAPI(title="Resume Tailor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_PROFILE_PATH = "data.json"
OUTPUT_DIR = "output"
TAILORED_DIR = "tailored"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TAILORED_DIR, exist_ok=True)

class TailorRequest(BaseModel):
    url: str = ""
    page_text: str = ""

class ExperienceItem(BaseModel):
    title: str
    organization: str
    location: str = ""
    address: str = ""
    dates: str
    bullets: list[str] = []

class PersonalInfoItem(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    address: dict = {}
    location: str = ""
    linkedin: str = ""
    github: str = ""
    skills: dict | list = {}

@app.get("/", response_class=HTMLResponse)
def root_ui():
    html_path = os.path.join("web", "index.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="Web UI not found.")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/profile")
def get_profile():
    if not os.path.exists(BASE_PROFILE_PATH):
        raise HTTPException(status_code=500, detail="Base profile data.json not found.")
    with open(BASE_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/profile/personal")
def update_personal_info(info: PersonalInfoItem):
    if not os.path.exists(BASE_PROFILE_PATH):
        raise HTTPException(status_code=500, detail="Base profile data.json not found.")

    with open(BASE_PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)

    profile["first_name"] = info.first_name
    profile["last_name"] = info.last_name
    profile["email"] = info.email
    profile["phone"] = info.phone
    profile["address"] = info.address
    profile["location"] = info.location or f"{info.address.get('city', '')}, {info.address.get('state', '')}".strip(", ")
    profile["linkedin"] = info.linkedin
    profile["github"] = info.github
    if info.skills:
        profile["skills"] = info.skills

    with open(BASE_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    return {"status": "success", "profile": profile}

@app.post("/api/experience")
def add_experience(item: ExperienceItem):
    if not os.path.exists(BASE_PROFILE_PATH):
        raise HTTPException(status_code=500, detail="Base profile data.json not found.")

    with open(BASE_PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)

    if "experience" not in profile:
        profile["experience"] = []

    profile["experience"].append(item.model_dump())

    with open(BASE_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    return {"status": "success", "count": len(profile["experience"])}

@app.delete("/api/experience/{index}")
def delete_experience(index: int):
    if not os.path.exists(BASE_PROFILE_PATH):
        raise HTTPException(status_code=500, detail="Base profile data.json not found.")

    with open(BASE_PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)

    if "experience" in profile and 0 <= index < len(profile["experience"]):
        removed = profile["experience"].pop(index)
        with open(BASE_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        return {"status": "success", "removed": removed}

    raise HTTPException(status_code=404, detail="Experience index out of bounds.")

@app.put("/api/experience/{index}")
def update_experience(index: int, item: ExperienceItem):
    if not os.path.exists(BASE_PROFILE_PATH):
        raise HTTPException(status_code=500, detail="Base profile data.json not found.")

    with open(BASE_PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)

    if "experience" in profile and 0 <= index < len(profile["experience"]):
        profile["experience"][index] = item.model_dump()
        with open(BASE_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        return {"status": "success", "updated": item.model_dump()}

    raise HTTPException(status_code=404, detail="Experience index out of bounds.")

@app.post("/api/tailor")
def api_tailor(req: TailorRequest):
    if not os.path.exists(BASE_PROFILE_PATH):
        raise HTTPException(status_code=500, detail="Base profile data.json not found.")

    with open(BASE_PROFILE_PATH, "r", encoding="utf-8") as f:
        base_profile = json.load(f)

    # 1. Extract job data
    if req.page_text and len(req.page_text.strip()) > 50:
        print(f"[*] Processing job from page text ({len(req.page_text.split())} words)")
        job_data = structure_job_with_llm(req.page_text)
    elif req.url:
        print(f"[*] Fetching job from URL: {req.url}")
        job_data, _ = process_job(req.url, is_url=True)
    else:
        raise HTTPException(status_code=400, detail="Neither url nor page_text was provided.")

    company = job_data.get("company") or "Company"
    title = job_data.get("title") or "Job"
    company_clean = re.sub(r"[^\w\-_]", "_", company).strip("_")

    first_name = base_profile.get("first_name", "Candidate")
    last_name = base_profile.get("last_name", "Resume")

    filename = f"{first_name}_{last_name}_{company_clean}_Resume.pdf"
    output_pdf_path = os.path.join(OUTPUT_DIR, filename)
    tailored_json_path = os.path.join(TAILORED_DIR, f"{first_name}_{last_name}_{company_clean}.json")

    # 2. Tailor profile
    print(f"[*] Tailoring resume for {title} at {company}")
    tailored_resume, changelog = tailor_resume(base_profile, job_data)

    # 3. Save JSON & compile PDF
    with open(tailored_json_path, "w", encoding="utf-8") as f:
        json.dump(tailored_resume, f, indent=2)

    success = compile_pdf(tailored_json_path, output_pdf_path)
    if not success:
        raise HTTPException(status_code=500, detail="Typst compilation failed.")

    return {
        "status": "success",
        "job": {
            "title": title,
            "company": company,
        },
        "changelog": changelog,
        "filename": filename,
        "download_url": f"http://127.0.0.1:8000/api/download/{filename}",
    }

@app.get("/api/download/{filename}")
def api_download(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename,
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
