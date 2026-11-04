import os
import sys
import re
import json
import argparse
import requests
from bs4 import BeautifulSoup
from llm_client import ask

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def clean_json_text(text: str) -> dict:
    """Extract and parse valid JSON from LLM output, handling markdown code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1)

    return json.loads(cleaned)

def fetch_html(url: str, timeout: int = 10) -> str:
    """Fetch raw HTML from a job URL with browser headers."""
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def extract_job_text_from_html(html: str, url: str = "") -> tuple[str, str, str]:
    """
    Extract readable text, candidate title, and company from HTML.
    Supports Next.js Greenhouse, Classic Greenhouse, Lever, and Universal fallback.
    Returns: (title_hint, company_hint, cleaned_text)
    """
    soup = BeautifulSoup(html, "lxml")
    title_hint = ""
    company_hint = ""

    # Strategy 1: Modern Greenhouse with __NEXT_DATA__
    next_data_tag = soup.find("script", id="__NEXT_DATA__")
    if next_data_tag and next_data_tag.string:
        try:
            payload = json.loads(next_data_tag.string)
            listing = payload.get("props", {}).get("pageProps", {}).get("listing", {})
            if listing:
                title_hint = listing.get("title") or listing.get("jobName", "")
                company_hint = listing.get("companyName", "")
                raw_markdown = listing.get("contentMarkdown") or listing.get("content", "")
                if raw_markdown:
                    # Content found in Next.js props
                    return title_hint, company_hint, raw_markdown
        except Exception:
            pass

    # Strategy 2: Lever postings (jobs.lever.co)
    if "jobs.lever.co" in url or soup.find("div", class_="posting-headline"):
        headline = soup.find("div", class_="posting-headline")
        if headline and headline.find("h2"):
            title_hint = headline.find("h2").get_text(strip=True)

        categories = soup.find("div", class_="posting-categories")
        cat_text = categories.get_text(separator=" | ", strip=True) if categories else ""

        section = soup.find("div", class_="section-wrapper") or soup.find("div", class_="section-page")
        if section:
            content_text = section.get_text(separator="\n", strip=True)
            full_text = f"Title: {title_hint}\nCategories: {cat_text}\n\n{content_text}"
            return title_hint, company_hint, full_text

    # Strategy 3: Classic Greenhouse
    if "boards.greenhouse.io" in url or soup.find(id="content"):
        app_title = soup.find("h1", class_="app-title")
        if app_title:
            title_hint = app_title.get_text(strip=True)
        co_tag = soup.find("span", class_="company-name")
        if co_tag:
            company_hint = co_tag.get_text(strip=True)
        content_div = soup.find(id="content")
        if content_div:
            return title_hint, company_hint, content_div.get_text(separator="\n", strip=True)

    # Strategy 4: Universal Pruner for arbitrary company career pages
    # Remove junk tags
    for tag in soup(["script", "style", "nav", "footer", "header", "svg", "noscript", "aside", "form"]):
        tag.decompose()

    # Try common main content wrappers
    main_el = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", role="main")
        or soup.find(id=re.compile(r"job|content|posting", re.I))
        or soup.find(class_=re.compile(r"job[-_]?description|posting[-_]?content", re.I))
        or soup.body
    )

    if soup.find("h1"):
        title_hint = soup.find("h1").get_text(strip=True)

    raw_text = main_el.get_text(separator="\n", strip=True) if main_el else soup.get_text(separator="\n", strip=True)
    # Collapse 3+ newlines into 2
    cleaned_text = re.sub(r"\n{3,}", "\n\n", raw_text)

    return title_hint, company_hint, cleaned_text

def structure_job_with_llm(raw_text: str, title_hint: str = "", company_hint: str = "") -> dict:
    """Use OpenRouter LLM to extract normalized JSON from unstructured job text."""
    prompt = f"""You are an expert technical recruiter and resume strategist.
Extract structured information from this job posting as JSON only (no markdown formatting, no explanations, no wrapping in codeblocks).

Return valid JSON with these exact fields:
- "title": Job title (e.g. "Software Engineer Intern")
- "company": Company name
- "location": Location or Remote status
- "experience_level": e.g. "Internship", "Entry-Level / New Grad", "Mid-Level", etc.
- "required_skills": list of required technical skills, languages, tools, frameworks, and degrees
- "preferred_skills": list of nice-to-have skills or qualifications
- "responsibilities": list of core responsibilities and day-to-day duties
- "keywords": list of high-priority keywords to optimize an ATS resume for this role
- "summary": a concise 2-3 sentence overview of what the team does and what they are looking for

Metadata Hints:
Title Hint: {title_hint}
Company Hint: {company_hint}

Job Posting Text:
{raw_text[:12000]}
"""
    result, usage, model, finish_reason = ask(prompt)
    structured = clean_json_text(result)
    return structured

def save_job(job_data: dict, output_dir: str = "jobs") -> str:
    """Save structured job data to a JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    company = job_data.get("company") or "Company"
    title = job_data.get("title") or "Job"
    slug = re.sub(r"[^\w\-_]", "_", f"{company}_{title}").strip("_")
    filename = os.path.join(output_dir, f"{slug}.json")

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(job_data, f, indent=2)

    return filename

def process_job(url_or_text: str, is_url: bool = True) -> tuple[dict, str]:
    """Fetch/receive job description, structure it via LLM, and save."""
    if is_url:
        print(f"[*] Fetching job posting from: {url_or_text}")
        html = fetch_html(url_or_text)
        title_hint, company_hint, text = extract_job_text_from_html(html, url=url_or_text)
    else:
        title_hint, company_hint = "", ""
        text = url_or_text

    print(f"[*] Extracted {len(text.split())} words of job text. Structuring with LLM...")
    job_data = structure_job_with_llm(text, title_hint, company_hint)
    saved_path = save_job(job_data)
    return job_data, saved_path

def main():
    parser = argparse.ArgumentParser(description="Scrape and structure job descriptions for resume tailoring.")
    parser.add_argument("url", nargs="?", default="", help="Job posting URL (e.g. Greenhouse, Lever, company site)")
    parser.add_argument("--paste", action="store_true", help="Paste raw job description text from clipboard/terminal")
    parser.add_argument("--file", type=str, help="Read job description text or HTML from a local file")

    args = parser.parse_args()

    if args.paste:
        print("Paste the job description below (enter EOF / Ctrl+D when finished):")
        raw_text = sys.stdin.read().strip()
        if not raw_text:
            print("Error: No text provided.")
            sys.exit(1)
        job_data, saved_path = process_job(raw_text, is_url=False)
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip().startswith("<") and "</html>" in content.lower():
            title_hint, company_hint, text = extract_job_text_from_html(content, url=args.file)
            job_data = structure_job_with_llm(text, title_hint, company_hint)
            saved_path = save_job(job_data)
        else:
            job_data, saved_path = process_job(content, is_url=False)
    elif args.url:
        job_data, saved_path = process_job(args.url, is_url=True)
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python job_scraper.py https://boards.greenhouse.io/stripe/jobs/8172508")
        print("  python job_scraper.py --paste")
        sys.exit(0)

    print("\n" + "=" * 50)
    print(f"Successfully processed: {job_data.get('title')} at {job_data.get('company')}")
    print(f"Saved to: {saved_path}")
    print("=" * 50)
    print(f"Location: {job_data.get('location')}")
    print(f"Experience Level: {job_data.get('experience_level')}")
    print(f"Required Skills ({len(job_data.get('required_skills', []))}): {', '.join(job_data.get('required_skills', [])[:5])}...")
    print(f"Keywords ({len(job_data.get('keywords', []))}): {', '.join(job_data.get('keywords', [])[:6])}...")

if __name__ == "__main__":
    main()
