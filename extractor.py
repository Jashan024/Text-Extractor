import re
import spacy

nlp = spacy.load("en_core_web_sm")

# Pattern: "City, ST"
LOCATION_PATTERN = re.compile(
    r'^([A-Za-z][A-Za-z .\'()-]+),\s*([A-Z]{2})$'
)

# Pattern: company/employer line — ends with a year range like "2020 - Present" or "2020 - 2023"
EMPLOYER_PATTERN = re.compile(
    r'\d{4}\s*-\s*(?:Present|\d{4})\s*$', re.IGNORECASE
)

# Standalone year-range lines like "2025 - Present" or "2022 - 2023"
YEAR_RANGE_PATTERN = re.compile(
    r'^\d{4}\s*-\s*(?:Present|\d{4})$', re.IGNORECASE
)

# Lines that are metadata / noise — skip these
SKIP_PATTERNS = [
    re.compile(r'^Relevant Work Experience$', re.IGNORECASE),
    re.compile(r'^Education$', re.IGNORECASE),
    re.compile(r'^Licenses and certifications$', re.IGNORECASE),
    re.compile(r'^Recently updated:', re.IGNORECASE),
    re.compile(r'^Active\s', re.IGNORECASE),
    re.compile(r'^\+\d+ more$'),
    re.compile(r'^Contacted via', re.IGNORECASE),
    re.compile(r'^Military\s*\(', re.IGNORECASE),
]

# Education-related keywords that indicate an education line, not a title
EDUCATION_KEYWORDS = [
    'bachelor', 'master', 'associate', 'diploma', 'certificate',
    'certification', 'b.s.', 'b.a.', 'm.s.', 'm.a.', 'bsn', 'msn',
    'm.b.a.', 'mba', 'phd', 'ph.d.', 'some college', 'high school',
    'cosmetologist', 'licensed practitioner nurse',
]

# Known certifications/licenses (short items that are NOT job titles)
CERT_PATTERN = re.compile(
    r'^(RN|LPN|LVN|CNA|BLS|ACLS|NIHSS|AED|CPR|CCRN|CPI|CNOR|'
    r'TNCC|ENPC|WCC|CHHA|ARNP|APN|APRN|SHRM|IV Certification|'
    r'Driver\'s License|Compact License|Graduate Nurse|'
    r'Paramedic License|Non-CDL Class C|Pharmacy Technician License|'
    r'Pharmacy Technician Certification|Licensed Nursing Home Administrator|'
    r'Certified Registered Nurse Practitioner|SHRM Certified Professional|'
    r'BLS Instructor Certification|Certified Case Manager|'
    r'First Aid Certification|Heartsaver Certification)$', re.IGNORECASE
)


def is_location_line(line):
    return bool(LOCATION_PATTERN.match(line.strip()))


def is_employer_line(line):
    return bool(EMPLOYER_PATTERN.search(line.strip()))


def is_year_range_line(line):
    return bool(YEAR_RANGE_PATTERN.match(line.strip()))


def is_skip_line(line):
    stripped = line.strip()
    if not stripped:
        return True
    for pat in SKIP_PATTERNS:
        if pat.search(stripped):
            return True
    return False


def is_education_line(line):
    lower = line.strip().lower()
    for kw in EDUCATION_KEYWORDS:
        if kw in lower:
            return True
    return False


def is_cert_line(line):
    return bool(CERT_PATTERN.match(line.strip()))


def is_name_line(line):
    """
    A name is 2-5 words, all alphabetic (hyphens/apostrophes/parens allowed),
    no 4-digit years, possibly with credential suffixes like MBA, SHRM-CP.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if re.search(r'\d{4}', stripped):
        return False

    # Strip credential suffixes
    name_part = re.sub(
        r',\s*(MBA|SHRM-CP|RN|BSN|MSN|PhD|MD|DO|NP|CRNP|DNP|LPN)'
        r'(\s*,\s*(MBA|SHRM-CP|RN|BSN|MSN|PhD|MD|DO|NP|CRNP|DNP|LPN))*\s*$',
        '', stripped, flags=re.IGNORECASE
    ).strip()

    words = name_part.split()
    if len(words) < 2 or len(words) > 6:
        return False
    for word in words:
        cleaned = re.sub(r'[().]', '', word)
        if not re.match(r'^[A-Za-z\'-]+$', cleaned):
            return False
    return True


def find_next_nonblank(lines, start):
    """Find the next non-blank line index starting from 'start'."""
    idx = start
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    return idx


def extract_entities(text):
    """
    Extract names, locations, and job titles from structured profile text.

    The data format has each profile as:
        Name                          (may appear TWICE — duplicate header)
        Name                          (duplicate — skip)
        City, ST
        Relevant Work Experience
        Job Title 1
        Employer, YYYY - Present
        Job Title 2
        Employer, YYYY - YYYY
        Education
        ...
        Licenses and certifications
        ...
        Recently updated: ...
        Active ...
    """
    lines = text.split('\n')
    people = []
    current_person = None
    in_education = False
    in_certs = False

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # --- Check for section markers (update state even if we also skip) ---
        if re.match(r'^Education$', line, re.IGNORECASE):
            in_education = True
            in_certs = False
            i += 1
            continue
        if re.match(r'^Licenses and certifications$', line, re.IGNORECASE):
            in_certs = True
            in_education = False
            i += 1
            continue
        if re.match(r'^Relevant Work Experience$', line, re.IGNORECASE):
            in_education = False
            in_certs = False
            i += 1
            continue

        # Skip other metadata lines
        if is_skip_line(line):
            i += 1
            continue

        # --- Try to detect a NEW PERSON ---
        # A new person starts with a name line, optionally followed by a
        # duplicate of the same name, then a "City, ST" location line.
        if is_name_line(line):
            # Look ahead: skip optional duplicate name, then expect location
            lookahead = find_next_nonblank(lines, i + 1)
            lookahead_line = lines[lookahead].strip() if lookahead < len(lines) else ''

            # If next line is a duplicate of this name, skip past it
            if lookahead_line == line:
                # duplicate name — look one more ahead for location
                lookahead2 = find_next_nonblank(lines, lookahead + 1)
                lookahead2_line = lines[lookahead2].strip() if lookahead2 < len(lines) else ''

                if is_location_line(lookahead2_line):
                    # NEW PERSON confirmed: Name + Duplicate + Location
                    if current_person:
                        people.append(current_person)
                    current_person = {
                        'name': line,
                        'location': lookahead2_line,
                        'titles': [],
                    }
                    in_education = False
                    in_certs = False
                    i = lookahead2 + 1  # skip past name, duplicate, location
                    continue

            # No duplicate — next line is directly the location
            elif is_location_line(lookahead_line):
                # NEW PERSON confirmed: Name + Location
                if current_person:
                    people.append(current_person)
                current_person = {
                    'name': line,
                    'location': lookahead_line,
                    'titles': [],
                }
                in_education = False
                in_certs = False
                i = lookahead + 1  # skip past name and location
                continue

        # --- Skip location lines that we already consumed above ---
        if is_location_line(line):
            i += 1
            continue

        # --- Skip employer/date lines ---
        if is_employer_line(line):
            i += 1
            continue

        # --- Skip standalone year range lines like "2025 - Present" ---
        if is_year_range_line(line):
            i += 1
            continue

        # --- If in education or certs section, skip everything ---
        if in_education or in_certs:
            i += 1
            continue

        # --- Otherwise, this is a JOB TITLE for the current person ---
        if current_person:
            if not is_cert_line(line) and not is_education_line(line):
                title = line.strip()
                if title and title not in current_person['titles']:
                    current_person['titles'].append(title)

        i += 1

    # Don't forget the last person
    if current_person:
        people.append(current_person)

    # Build output
    names = []
    locations = []
    titles = []
    structured = []

    for person in people:
        name = person['name']
        loc = person['location']
        ptitles = person['titles']

        if name and name not in names:
            names.append(name)
        if loc and loc not in locations:
            locations.append(loc)
        for t in ptitles:
            if t not in titles:
                titles.append(t)

        structured.append({
            'name': name,
            'location': loc,
            'titles': ptitles,
        })

    return {
        "names": names,
        "locations": locations,
        "titles": titles,
        "people": structured,
    }
