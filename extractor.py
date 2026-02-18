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


def extract_entities(text, source='indeed'):
    """Route to the correct parser based on source."""
    if source == 'signalhire':
        return extract_signalhire(text)
    return extract_indeed(text)


# =========================================================================
# SignalHire Parser
# =========================================================================

# Profile start: "* X" where X is a single capital letter, OR just a single capital letter
SH_PROFILE_START = re.compile(r'^(?:\*\s+)?[A-Z]$')

# Title line: ends with " at"
SH_TITLE_LINE = re.compile(r'^(.+)\s+at$', re.IGNORECASE)

# Company line: wrapped in double underscores
SH_COMPANY_LINE = re.compile(r'^__(.+)__$')

# Location line: "City, State, United States" or "City, State Area, United States"
SH_LOCATION_LINE = re.compile(
    r'^[A-Za-z .\'()-]+,\s*[A-Za-z ]+(?:\s+Area)?,\s*United States$'
)

# Noise patterns to skip
SH_SKIP_PATTERNS = [
    re.compile(r'^Watched$', re.IGNORECASE),
    re.compile(r'^\d+\s+years?\s+exp$', re.IGNORECASE),
    re.compile(r'^Prev$', re.IGNORECASE),
    re.compile(r'^Skills$', re.IGNORECASE),
    re.compile(r'^\s*\*\s*$'),                # indented bullet artifacts
    re.compile(r'\d+\s+more$'),               # "2 more", "7 more" etc.
    re.compile(r'^Standard Search', re.IGNORECASE),
    re.compile(r'^View tips', re.IGNORECASE),
    re.compile(r'^Saved searches', re.IGNORECASE),
    re.compile(r'^Search history', re.IGNORECASE),
    re.compile(r'^Location$', re.IGNORECASE),
    re.compile(r'^Radius:', re.IGNORECASE),
    re.compile(r'^Title$', re.IGNORECASE),
    re.compile(r'^Current and Past', re.IGNORECASE),
    re.compile(r'^Manage Profiles', re.IGNORECASE),
    re.compile(r'^Show "', re.IGNORECASE),
    re.compile(r'^Exclude "', re.IGNORECASE),
    re.compile(r'^Revealed', re.IGNORECASE),
    re.compile(r'^Not Revealed', re.IGNORECASE),
    re.compile(r'^All Revealed', re.IGNORECASE),
    re.compile(r'^Search in', re.IGNORECASE),
    re.compile(r'^Advanced search', re.IGNORECASE),
    re.compile(r'^Company$', re.IGNORECASE),
    re.compile(r'^Years of work', re.IGNORECASE),
    re.compile(r'^Industry$', re.IGNORECASE),
]


def is_sh_skip(line):
    """Check if a line is SignalHire noise/metadata."""
    stripped = line.strip()
    if not stripped:
        return True
    for pat in SH_SKIP_PATTERNS:
        if pat.search(stripped):
            return True
    return False


def extract_signalhire(text):
    """
    Extract names, locations, and job titles from SignalHire profile text.

    Each profile follows this structure:
        * X                          (single-letter initial — profile start)
        Full Name
        [Watched]                    (optional)
        [Job Title at]               (optional — title ends with " at")
        [__Company Name__]           (optional — wrapped in double underscores)
        City, State, United States   (location)
        [N years exp]                (optional metadata)
        [Prev]                       (optional)
        [previous jobs ...]          (optional)
        [Skills]                     (optional)
        [skills list ...]            (optional)
    """
    lines = text.split('\n')
    people = []
    i = 0

    # Skip header/filter noise at the top until first profile marker
    while i < len(lines):
        line = lines[i].strip()
        if SH_PROFILE_START.match(line):
            break
        i += 1

    while i < len(lines):
        line = lines[i].strip()

        # --- Detect profile start: "* X" ---
        if SH_PROFILE_START.match(line):
            i += 1  # skip the "* X" line

            # Next non-blank line is the NAME
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines):
                break

            name = lines[i].strip()
            i += 1

            title = ''
            location = ''

            # Walk through the remaining lines of this profile
            while i < len(lines):
                curr = lines[i].strip()

                # If we hit the next profile, stop
                if SH_PROFILE_START.match(curr):
                    break

                # Skip blanks
                if not curr:
                    i += 1
                    continue

                # Skip "Watched"
                if curr.lower() == 'watched':
                    i += 1
                    continue

                # Title line: "Something at"
                title_match = SH_TITLE_LINE.match(curr)
                if title_match and not title:
                    title = title_match.group(1).strip()
                    i += 1
                    continue

                # Company line: "__Company__" — skip (we capture title, not company)
                if SH_COMPANY_LINE.match(curr):
                    i += 1
                    continue

                # Location line
                if SH_LOCATION_LINE.match(curr) and not location:
                    location = curr
                    i += 1
                    # After location, skip remaining metadata until next profile
                    while i < len(lines):
                        rest = lines[i].strip()
                        if SH_PROFILE_START.match(rest):
                            break
                        i += 1
                    break

                # Skip known noise
                if is_sh_skip(curr):
                    i += 1
                    continue

                # Skip skills/prev content lines (comma-heavy lines)
                if ',' in curr and len(curr.split(',')) >= 3:
                    i += 1
                    continue

                # Unknown line — skip
                i += 1

            # Build the person
            if name:
                person = {
                    'name': name,
                    'location': location,
                    'titles': [title] if title else [],
                }
                people.append(person)

            continue

        i += 1

    # Build output (same format as Indeed parser)
    return _build_output(people)


# =========================================================================
# Indeed Parser
# =========================================================================

def extract_indeed(text):
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

    return _build_output(people)


# =========================================================================
# Shared output builder
# =========================================================================

def _build_output(people):
    """Build the standard output dict from a list of person dicts."""
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
