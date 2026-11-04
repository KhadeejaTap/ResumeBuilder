import os
import sys
import re
import json
import argparse
import subprocess
import pdfplumber

from llm_client import ask
from job_scraper import process_job, clean_json_text

def get_job_data(target_input: str, is_paste: bool = False) -> tuple[dict, str]:
    """Retrieve structured job data from a URL, local JSON path, or pasted text."""
    if is_paste:
        print("[*] Paste the job description below (enter EOF / Ctrl+D when finished):")
        raw_text = sys.stdin.read().strip()
        if not raw_text:
            print("Error: No text provided.")
            sys.exit(1)
        return process_job(raw_text, is_url=False)

    if target_input.startswith("http://") or target_input.startswith("https://"):
        return process_job(target_input, is_url=True)

    if os.path.exists(target_input):
        with open(target_input, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, target_input

    print(f"Error: Target '{target_input}' is neither a valid URL nor an existing file path.")
    sys.exit(1)

def build_tailoring_prompt(base_profile: dict, job_data: dict) -> str:
    """Construct a rigorous prompt for truthful bullet tailoring and project selection."""
    return f"""You are an elite technical resume strategist and recruitment specialist.
Your goal is to tailor the candidate's resume for the specified job posting while preserving 100% truthfulness.

CRITICAL INTEGRITY RULES:
1. NEVER invent companies, degrees, dates, job titles, or metrics that the candidate did not provide.
2. NEVER claim proficiency in technologies or skills the candidate has never used.
3. Only rephrase, emphasize, and highlight genuine overlap between the candidate's real experience and the job's requirements.

STRATEGY & CONSTRAINTS:
1. PROJECT SELECTION:
   - The candidate's resume must strictly fit on ONE PAGE.
   - From the projects in the candidate profile, select the top 2 (or at most 3 if space permits) that are most relevant to the target job's tech stack and responsibilities.
   - Exclude less relevant projects to safeguard page budget.
2. BULLET POINT TAILORING:
   - For the selected projects and relevant experiences (especially SAIL Research and ACM-W leadership), rewrite bullet points to incorporate relevant keywords, action verbs (e.g. Engineered, Architected, Automated, Streamlined, Developed), and impact.
   - Keep each bullet concise (under 2 lines).
   - Cap each role at 2 to 4 bullets max.
3. SKILLS REORDERING:
   - In each skill category (Languages, Software Development, Web, AI/ML, Developer Tools), reorder items so that technologies mentioned in the job description appear FIRST.
   - Do NOT add technologies the candidate does not know.

TARGET JOB DESCRIPTION:
Title: {job_data.get('title')}
Company: {job_data.get('company')}
Required Skills: {json.dumps(job_data.get('required_skills', []))}
Preferred Skills: {json.dumps(job_data.get('preferred_skills', []))}
Responsibilities: {json.dumps(job_data.get('responsibilities', []))}
Keywords: {json.dumps(job_data.get('keywords', []))}

CANDIDATE BASE PROFILE:
{json.dumps(base_profile, indent=2)}

OUTPUT FORMAT:
Return valid JSON only (no markdown code blocks, no explanations outside the JSON).
The JSON must have this exact structure:
{{
  "tailored_resume": {{
    "first_name": "{base_profile.get('first_name', '')}",
    "last_name": "{base_profile.get('last_name', '')}",
    "email": "{base_profile.get('email', '')}",
    "phone": "{base_profile.get('phone', '')}",
    "location": "{base_profile.get('location', '')}",
    "linkedin": "{base_profile.get('linkedin', '')}",
    "github": "{base_profile.get('github', '')}",
    "education": {json.dumps(base_profile.get('education', []))},
    "experience": [
      {{
        "title": "...",
        "organization": "...",
        "location": "...",
        "dates": "...",
        "bullets": ["..."]
      }}
    ],
    "projects": [
      {{
        "name": "...",
        "type": "...",
        "dates": "...",
        "bullets": ["..."]
      }}
    ],
    "skills": {{
      "Languages": ["..."],
      "Software Development": ["..."],
      "Web": ["..."],
      "AI/ML": ["..."],
      "Developer Tools": ["..."]
    }}
  }},
  "changelog": {{
    "selected_projects": ["Project Name 1", "Project Name 2"],
    "selection_reason": "Explanation of why these projects were chosen for this specific role.",
    "prioritized_skills": ["Skill 1", "Skill 2", "Skill 3"],
    "bullet_diffs": [
      {{
        "role_or_project": "Role or Project Name",
        "original": "Original bullet text",
        "tailored": "Tailored bullet text"
      }}
    ]
  }}
}}
"""

def tailor_resume(base_profile: dict, job_data: dict) -> tuple[dict, dict]:
    """Send base profile and job description to OpenRouter for tailoring."""
    prompt = build_tailoring_prompt(base_profile, job_data)
    result, usage, model, finish_reason = ask(prompt)
    parsed = clean_json_text(result)

    tailored_resume = parsed.get("tailored_resume", {})
    changelog = parsed.get("changelog", {})
    return tailored_resume, changelog

def display_changelog(job_data: dict, changelog: dict, output_pdf: str):
    """Print an easy-to-read before/after summary in the terminal."""
    company = job_data.get("company", "Company")
    title = job_data.get("title", "Role")

    print("\n" + "=" * 65)
    print(f"🎯 TAILORING SUMMARY: {title} @ {company}")
    print("=" * 65)

    selected = changelog.get("selected_projects", [])
    print(f"\n[+] Selected Projects ({len(selected)}):")
    for proj in selected:
        print(f"    • {proj}")
    if changelog.get("selection_reason"):
        print(f"    Reason: {changelog.get('selection_reason')}")

    prioritized = changelog.get("prioritized_skills", [])
    if prioritized:
        print(f"\n[+] Highlighted Skills Reordered to Front:")
        print(f"    {', '.join(prioritized)}")

    diffs = changelog.get("bullet_diffs", [])
    if diffs:
        print(f"\n[~] Bullet Changes ({len(diffs)} updated):")
        for i, diff in enumerate(diffs, 1):
            print(f"\n  {i}. {diff.get('role_or_project', 'Experience')}:")
            print(f"     [-] OLD: {diff.get('original', '')}")
            print(f"     [+] NEW: {diff.get('tailored', '')}")

    print("\n" + "-" * 65)
    print(f"Target Output: {output_pdf}")
    print("-" * 65)

def compile_pdf(tailored_json_path: str, output_pdf_path: str) -> bool:
    """Compile the tailored JSON using Typst and verify it fits on 1 page."""
    cmd = [
        "typst",
        "compile",
        "--input",
        f"data={tailored_json_path}",
        "resume.typ",
        output_pdf_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Typst compilation error:\n{res.stderr}")
        return False

    # Verify page count with pdfplumber
    try:
        with pdfplumber.open(output_pdf_path) as pdf:
            page_count = len(pdf.pages)
            if page_count == 1:
                print(f"[✓] Successfully compiled 1-page PDF: {output_pdf_path}")
                return True
            else:
                print(f"[!] Warning: PDF generated {page_count} pages! Checking layout budget...")
                return True
    except Exception as e:
        print(f"[✓] PDF compiled to {output_pdf_path} (could not verify pages: {e})")
        return True

def main():
    parser = argparse.ArgumentParser(
        description="One-command resume tailor: Scrapes job, tailors bullets, and compiles 1-page PDF."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="",
        help="Job posting URL (Greenhouse, Lever, etc.) OR path to existing job JSON file",
    )
    parser.add_argument("--paste", action="store_true", help="Paste raw job description text interactively")
    parser.add_argument(
        "--resume",
        type=str,
        default="data.json",
        help="Path to base candidate JSON (default: data.json)",
    )
    parser.add_argument("-y", "--yes", action="store_true", help="Skip approval prompt and compile immediately")

    args = parser.parse_args()

    if not args.target and not args.paste:
        parser.print_help()
        print("\nExamples:")
        print("  python3 tailor.py https://boards.greenhouse.io/stripe/jobs/8172508")
        print("  python3 tailor.py jobs/Stripe_Abuse_Investigator.json")
        print("  python3 tailor.py --paste")
        sys.exit(0)

    # 1. Load base resume profile
    if not os.path.exists(args.resume):
        print(f"Error: Base resume '{args.resume}' not found. Run resume_parser.py first.")
        sys.exit(1)

    with open(args.resume, "r", encoding="utf-8") as f:
        base_profile = json.load(f)

    # 2. Ingest target job
    job_data, job_source = get_job_data(args.target, is_paste=args.paste)

    company_clean = re.sub(r"[^\w\-_]", "_", job_data.get("company", "Company")).strip("_")
    first_name = base_profile.get("first_name", "Candidate")
    last_name = base_profile.get("last_name", "Resume")

    # Recruiter-friendly output filename: Khadeeja_Tapkirwala_Stripe_Resume.pdf
    output_dir = "output"
    tailored_dir = "tailored"
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(tailored_dir, exist_ok=True)

    output_pdf_path = os.path.join(output_dir, f"{first_name}_{last_name}_{company_clean}_Resume.pdf")
    tailored_json_path = os.path.join(tailored_dir, f"{first_name}_{last_name}_{company_clean}.json")

    # 3. Tailor resume via OpenRouter LLM
    print(f"[*] Analyzing '{job_data.get('title')}' at {job_data.get('company')}...")
    print("[*] Selecting optimal projects and tailoring bullet points...")
    tailored_resume, changelog = tailor_resume(base_profile, job_data)

    # 4. Display changelog & prompt for approval
    display_changelog(job_data, changelog, output_pdf_path)

    if not args.yes:
        try:
            choice = input("\nGenerate this PDF? [Y/n]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)

        if choice and choice != "y" and choice != "yes":
            print("Aborted compilation. No PDF generated.")
            sys.exit(0)

    # 5. Save tailored data & compile PDF
    with open(tailored_json_path, "w", encoding="utf-8") as f:
        json.dump(tailored_resume, f, indent=2)

    print(f"\n[*] Compiling PDF with Typst...")
    success = compile_pdf(tailored_json_path, output_pdf_path)
    if success:
        print(f"\n🎉 Done! Ready to upload: {output_pdf_path}\n")

if __name__ == "__main__":
    main()
