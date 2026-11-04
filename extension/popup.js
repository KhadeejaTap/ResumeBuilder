const SERVER_URL = "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", async () => {
  const tabInfoEl = document.getElementById("tab-info");
  const autoapplyBtn = document.getElementById("autoapply-btn");
  const statusEl = document.getElementById("status");
  const applyResultsEl = document.getElementById("apply-results");
  const applyLogEl = document.getElementById("apply-log");

  let activeTab = null;

  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs && tabs[0]) {
      activeTab = tabs[0];
      tabInfoEl.textContent = activeTab.url || "Unknown URL";
    }
  } catch (err) {
    tabInfoEl.textContent = "Error detecting tab";
  }

  // AUTO-APPLY
  autoapplyBtn.addEventListener("click", async () => {
    if (!activeTab || !activeTab.id) {
      statusEl.textContent = "Error: No active tab found.";
      return;
    }

    autoapplyBtn.disabled = true;
    statusEl.textContent = "Fetching candidate profile...";
    applyResultsEl.classList.add("hidden");

    let profile = null;
    try {
      const res = await fetch(`${SERVER_URL}/api/profile`);
      if (!res.ok) throw new Error("Could not load profile from server.");
      profile = await res.json();
    } catch (e) {
      statusEl.textContent = `Error: ${e.message}. Is server running?`;
      autoapplyBtn.disabled = false;
      return;
    }

    statusEl.textContent = "Detecting application form and filling...";

    try {
      const injectionResults = await chrome.scripting.executeScript({
        target: { tabId: activeTab.id },
        func: executeAutofillInTab,
        args: [profile],
      });

      const logs = injectionResults && injectionResults[0] ? injectionResults[0].result : [];
      statusEl.textContent = `Auto-apply finished: ${logs.length} items logged.`;
      applyLogEl.textContent = logs.join("\n") || "No matching form fields found on this page.";
      applyResultsEl.classList.remove("hidden");
    } catch (err) {
      statusEl.textContent = `Auto-apply error: ${err.message}`;
    } finally {
      autoapplyBtn.disabled = false;
    }
  });
});

// ------------------------------------------------------------------
// Injected Autofill Engine: Runs directly inside the active tab
// ------------------------------------------------------------------
function executeAutofillInTab(profile) {
  const logs = [];

  function setFieldValue(el, val) {
    if (!el || val === undefined || val === null) return false;
    el.focus();

    const proto = el instanceof HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const nativeSetter = Object.getOwnPropertyDescriptor(proto, "value")?.set;

    if (nativeSetter) {
      nativeSetter.call(el, val);
    } else {
      el.value = val;
    }

    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.blur();
    return true;
  }

  function setSelectValue(el, targetText) {
    if (!el || !targetText) return false;
    el.focus();
    const needle = targetText.toLowerCase();
    for (const opt of el.options) {
      if (opt.text.toLowerCase().includes(needle) || opt.value.toLowerCase().includes(needle)) {
        el.value = opt.value;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        el.blur();
        return true;
      }
    }
    el.blur();
    return false;
  }

  function setCheckbox(el, checked = true) {
    if (!el) return false;
    if (el.checked !== checked) {
      el.click();
      el.checked = checked;
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }
    return true;
  }

  function findAndFill(selectors, value, fieldName) {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && !el.disabled && el.offsetParent !== null) {
        if (setFieldValue(el, value)) {
          logs.push(`Filled ${fieldName}: ${value}`);
          return true;
        }
      }
    }
    return false;
  }

  const hostname = window.location.hostname.toLowerCase();
  let platform = "Generic";
  if (hostname.includes("greenhouse.io")) platform = "Greenhouse";
  else if (hostname.includes("ashbyhq.com")) platform = "Ashby";
  else if (hostname.includes("myworkdayjobs.com")) platform = "Workday";

  logs.push(`Platform detected: ${platform}`);

  const fullName = `${profile.first_name || ""} ${profile.last_name || ""}`.trim();
  const phone = profile.phone || "";
  const email = profile.email || "";
  const location = profile.location || "";
  const linkedin = profile.linkedin ? (profile.linkedin.startsWith("http") ? profile.linkedin : `https://${profile.linkedin}`) : "";
  const github = profile.github ? (profile.github.startsWith("http") ? profile.github : `https://${profile.github}`) : "";

  // ---------------- 1. CONTACT INFO ----------------
  findAndFill([
    'input[data-automation-id="legalNameSection_firstName"]',
    'input[data-automation-id="firstName"]',
    '#first_name',
    'input[name="first_name"]',
    'input[name="firstName"]',
    'input[autocomplete="given-name"]',
  ], profile.first_name, "First Name");

  findAndFill([
    'input[data-automation-id="legalNameSection_lastName"]',
    'input[data-automation-id="lastName"]',
    '#last_name',
    'input[name="last_name"]',
    'input[name="lastName"]',
    'input[autocomplete="family-name"]',
  ], profile.last_name, "Last Name");

  findAndFill([
    'input[name="name"]',
    'input[name="fullName"]',
    '#name',
    'input[autocomplete="name"]',
  ], fullName, "Full Name");

  findAndFill([
    'input[data-automation-id="email"]',
    'input[data-automation-id="email-input"]',
    '#email',
    'input[name="email"]',
    'input[type="email"]',
    'input[autocomplete="email"]',
  ], email, "Email");

  findAndFill([
    'input[data-automation-id="phone-number"]',
    'input[data-automation-id="phoneNumber"]',
    '#phone',
    'input[name="phone"]',
    'input[name="phoneNumber"]',
    'input[type="tel"]',
    'input[autocomplete="tel"]',
  ], phone, "Phone");

  findAndFill([
    'input[name="urls.LinkedIn"]',
    'input[id*="linkedin" i]',
    'input[name*="linkedin" i]',
    'input[placeholder*="linkedin" i]',
    'input[data-automation-id*="linkedin" i]',
  ], linkedin, "LinkedIn");

  findAndFill([
    'input[name="urls.GitHub"]',
    'input[id*="github" i]',
    'input[name*="github" i]',
    'input[placeholder*="github" i]',
    'input[data-automation-id*="github" i]',
  ], github, "GitHub");

  // ---------------- USER ADDRESS (FOR WORKDAY / JOB SITES) ----------------
  const userAddr = profile.address || {};
  const street = userAddr.street || "";
  const city = userAddr.city || (location ? location.split(",")[0].trim() : "");
  const state = userAddr.state || (location && location.includes(",") ? location.split(",")[1].trim() : "");
  const zip = userAddr.postal_code || "";
  const country = userAddr.country || "United States";

  if (street) {
    findAndFill([
      'input[data-automation-id="addressSection_addressLine1"]',
      'input[data-automation-id="addressLine1"]',
      'input[data-automation-id="streetAddress"]',
      'input[id*="addressLine1" i]',
      'input[name*="addressLine1" i]',
      'input[placeholder*="street" i]',
      'input[placeholder*="address line 1" i]',
    ], street, "Street Address");
  }

  findAndFill([
    'input[data-automation-id="addressSection_city"]',
    'input[data-automation-id="city"]',
    'input[name="city"]',
    'input[id*="city" i]',
    '#city',
    'input[placeholder*="city" i]',
  ], city || location, "City");

  if (state) {
    const regionSelect = document.querySelector('select[data-automation-id="addressSection_countryRegion"], select[name*="region" i], select[name*="state" i]');
    if (regionSelect) {
      if (setSelectValue(regionSelect, state)) {
        logs.push(`State/Region: Selected ${state}`);
      }
    } else {
      findAndFill([
        'input[data-automation-id="addressSection_countryRegion"]',
        'input[data-automation-id="region"]',
        'input[name*="region" i]',
        'input[name*="state" i]',
      ], state, "State/Region");
    }
  }

  if (zip) {
    findAndFill([
      'input[data-automation-id="addressSection_postalCode"]',
      'input[data-automation-id="postalCode"]',
      'input[name*="postalCode" i]',
      'input[name*="zip" i]',
      'input[placeholder*="zip" i]',
      'input[placeholder*="postal" i]',
    ], zip, "Postal Code");
  }

  const countryEl = document.querySelector('select[data-automation-id="addressSection_country"], select[name*="country" i]');
  if (countryEl) {
    setSelectValue(countryEl, country);
  }

  // ---------------- 2. WORK EXPERIENCE ----------------
  const experiences = profile.experience || [];
  if (experiences.length > 0) {
    const jobTitleInputs = Array.from(document.querySelectorAll(
      'input[data-automation-id="jobTitle"], input[name*="jobTitle" i], input[id*="jobTitle" i], input[name*="experience[0].title" i]'
    )).filter(el => !el.disabled && el.offsetParent !== null);

    const companyInputs = Array.from(document.querySelectorAll(
      'input[data-automation-id="company"], input[name*="company" i], input[id*="company" i], input[name*="employer" i]'
    )).filter(el => !el.disabled && el.offsetParent !== null);

    const locationInputs = Array.from(document.querySelectorAll(
      'input[data-automation-id="location"], input[name*="experience[0].location" i]'
    )).filter(el => !el.disabled && el.offsetParent !== null);

    const addressInputs = Array.from(document.querySelectorAll(
      'input[data-automation-id="address"], input[data-automation-id="companyAddress"], input[data-automation-id="workAddress"], input[name*="companyAddress" i], input[name*="employerAddress" i]'
    )).filter(el => !el.disabled && el.offsetParent !== null);

    const descTextareas = Array.from(document.querySelectorAll(
      'textarea[data-automation-id="description"], textarea[name*="description" i], textarea[name*="experience" i]'
    )).filter(el => !el.disabled && el.offsetParent !== null);

    const currentCheckboxes = Array.from(document.querySelectorAll(
      'input[data-automation-id="currentlyWorkHere"], input[name*="currentlyWorkHere" i], input[id*="current" i]'
    )).filter(el => !el.disabled && el.offsetParent !== null);

    const cardsToFill = Math.max(jobTitleInputs.length, companyInputs.length, descTextareas.length);
    for (let i = 0; i < Math.min(cardsToFill, experiences.length); i++) {
      const exp = experiences[i];
      if (jobTitleInputs[i]) {
        setFieldValue(jobTitleInputs[i], exp.title);
        logs.push(`Work Experience [${i + 1}] Title: ${exp.title}`);
      }
      if (companyInputs[i]) {
        setFieldValue(companyInputs[i], exp.organization);
        logs.push(`Work Experience [${i + 1}] Company: ${exp.organization}`);
      }
      if (locationInputs[i]) {
        setFieldValue(locationInputs[i], exp.location);
      }
      if (addressInputs[i] && (exp.address || exp.location)) {
        setFieldValue(addressInputs[i], exp.address || exp.location);
        logs.push(`Work Experience [${i + 1}] Address: ${exp.address || exp.location}`);
      }
      if (descTextareas[i]) {
        const descText = (exp.bullets || []).join("\n• ");
        setFieldValue(descTextareas[i], `• ${descText}`);
        logs.push(`Work Experience [${i + 1}] Bullets: ${exp.bullets.length} points added`);
      }
      if (currentCheckboxes[i] && (exp.dates || "").toLowerCase().includes("present")) {
        setCheckbox(currentCheckboxes[i], true);
        logs.push(`Work Experience [${i + 1}] Currently Work Here: Checked`);
      }
    }

    if (cardsToFill === 0) {
      const primaryExp = experiences[0];
      findAndFill(['input[id*="current_company" i]', 'input[name*="recent_employer" i]'], primaryExp.organization, "Current Company");
      findAndFill(['input[id*="current_title" i]', 'input[name*="recent_title" i]'], primaryExp.title, "Current Role Title");
    }
  }

  // ---------------- 3. SKILLS ----------------
  let flatSkills = [];
  if (profile.skills && typeof profile.skills === "object" && !Array.isArray(profile.skills)) {
    for (const group of Object.values(profile.skills)) {
      if (Array.isArray(group)) flatSkills.push(...group);
    }
  } else if (Array.isArray(profile.skills)) {
    flatSkills = profile.skills;
  }

  const skillsString = flatSkills.join(", ");

  const skillFilled = findAndFill([
    'div[data-automation-id="skillsSection"] textarea',
    'textarea[data-automation-id="skills"]',
    'textarea[name*="skill" i]',
    'textarea[id*="skill" i]',
    'textarea[placeholder*="skill" i]',
    'input[data-automation-id="skills"]',
    'input[name*="skill" i]',
    'input[id*="skill" i]',
    'input[placeholder*="skill" i]',
  ], skillsString, "Skills");

  if (!skillFilled) {
    const searchBox = document.querySelector('div[data-automation-id="skillsSection"] input[data-automation-id="searchBox"]');
    if (searchBox) {
      setFieldValue(searchBox, flatSkills.slice(0, 5).join(", "));
      logs.push("Skills: Populated top skills into search box");
    }
  }

  // ---------------- 4. LANGUAGES ----------------
  const languages = profile.languages_spoken || [{ language: "English", proficiency: "Native / Bilingual" }];
  const primaryLang = languages[0];

  const langSelect = document.querySelector(
    'select[data-automation-id="language"], select[name*="language" i], select[id*="language" i]'
  );
  if (langSelect) {
    if (setSelectValue(langSelect, primaryLang.language)) {
      logs.push(`Language: Selected ${primaryLang.language}`);
    }
  } else {
    findAndFill([
      'input[data-automation-id="language"]',
      'input[name*="language" i]',
      'input[id*="language" i]',
      'input[placeholder*="language" i]',
    ], primaryLang.language, "Language");
  }

  const profSelect = document.querySelector(
    'select[data-automation-id="languageProficiency"], select[name*="proficiency" i], select[id*="proficiency" i]'
  );
  if (profSelect) {
    if (setSelectValue(profSelect, "Native") || setSelectValue(profSelect, "Fluent") || setSelectValue(profSelect, "Bilingual")) {
      logs.push(`Language Proficiency: Selected Native/Fluent`);
    }
  }

  // ---------------- 5. EDUCATION ----------------
  if (profile.education && profile.education.length > 0) {
    const edu = profile.education[0];
    findAndFill([
      'input[data-automation-id="school"]',
      'input[data-automation-id="institution"]',
      'input[id*="school" i]',
      'input[name*="school" i]',
      'input[id*="university" i]',
      'input[name*="education" i]',
    ], edu.institution, "School / University");

    findAndFill([
      'input[data-automation-id="degree"]',
      'input[name*="degree" i]',
      'input[id*="degree" i]',
    ], profile.degree_type || edu.degree, "Degree");

    findAndFill([
      'input[data-automation-id="field-of-study"]',
      'input[name*="major" i]',
      'input[name*="fieldOfStudy" i]',
      'input[id*="major" i]',
    ], profile.major || "Computer Science", "Major / Field of Study");
  }

  // ---------------- 6. WORK AUTHORIZATION ----------------
  const authRadio = document.querySelector('input[type="radio"][value*="yes" i][name*="authorized" i], input[type="radio"][value*="yes" i][name*="sponsorship" i]');
  if (authRadio) {
    authRadio.click();
    logs.push("Work Authorization: Checked 'Yes'");
  }

  return logs;
}
