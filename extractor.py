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
    if source == 'linkedin_xray':
        return extract_linkedin_xray(text)
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
# LinkedIn X-ray Parser
# =========================================================================

# Profile start: "LinkedIn · Name" or "LinkedIn · Name credentials"
LI_PROFILE_LINE = re.compile(r'^LinkedIn\s*[·•]\s*(.+)$')

# Follower count line: "90+ followers" or "1,200 followers"
LI_FOLLOWERS_LINE = re.compile(r'^\d[\d,]*\+?\s+followers?$', re.IGNORECASE)

# Header line: "Name - Title at Company..." (Google search result title)
LI_HEADER_LINE = re.compile(r'^(.+?)\s+-\s+(.+)$')

# Credential suffixes to strip from names
LI_CREDENTIAL_PATTERN = re.compile(
    r'[\s,]+(BS|BSN|MSN|MBA|RN|LPN|MD|DO|NP|CRNP|DNP|PhD|PharmD|'
    r'MS|MA|BA|APRN|FNP|FNP-C|FNP-BC|ACNP|CNS|CRNA|PA-C|PA|'
    r'SHRM-CP|SHRM-SCP|CPA|JD|DDS|DMD|OD|DC|DPT|DPM|'
    r'MPH|MHA|MEd|EdD|LCSW|LMSW|LPC|LMFT|BCBA|OTR|'
    r'B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|M\.?B\.?A\.?|'
    r'Ph\.?D\.?)'
    r'([\s,]+(BS|BSN|MSN|MBA|RN|LPN|MD|DO|NP|CRNP|DNP|PhD|PharmD|'
    r'MS|MA|BA|APRN|FNP|FNP-C|FNP-BC|ACNP|CNS|CRNA|PA-C|PA|'
    r'SHRM-CP|SHRM-SCP|CPA|JD|DDS|DMD|OD|DC|DPT|DPM|'
    r'MPH|MHA|MEd|EdD|LCSW|LMSW|LPC|LMFT|BCBA|OTR|'
    r'B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|M\.?B\.?A\.?|'
    r'Ph\.?D\.?))*\s*$', re.IGNORECASE
)

# US state names for location detection
US_STATES = {
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york',
    'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west virginia', 'wisconsin', 'wyoming', 'district of columbia',
}


def strip_li_credentials(name):
    """Strip credential suffixes from a LinkedIn name."""
    return LI_CREDENTIAL_PATTERN.sub('', name).strip().rstrip(',').strip()


def extract_li_location(text):
    """
    Extract a US location from a middle-dot-separated line or plain text.
    Looks for "City, State, United States" or "City, State" patterns.
    """
    # Clean up __Read more__ artifacts and trailing dots
    cleaned = re.sub(r'_+Read_*\s*more_*', '', text).strip().rstrip('.')

    # Also try to find location via regex search in the full text
    # (handles cases where location is embedded in description without middle dots)
    # "City, State, United States" embedded anywhere
    embedded = re.search(
        r'([A-Z][A-Za-z .\'()-]+,\s*[A-Z][A-Za-z ]+,\s*United States)',
        cleaned
    )

    # Split by middle dot separator AND by ". " (sentence separator)
    segments = re.split(r'\s*[·•]\s*|(?<=\.)\s+', cleaned)
    for seg in segments:
        seg = seg.strip().rstrip('.')
        if not seg:
            continue
        # "City, State, United States"
        m = re.match(
            r'^([A-Za-z][A-Za-z .\'()-]+),\s*([A-Za-z][A-Za-z ]+?),\s*United States$',
            seg
        )
        if m:
            state_part = m.group(2).strip()
            if state_part.lower() in US_STATES:
                return seg
        # "City, State" (2-letter code) — but NOT credentials like "BSN, RN"
        m2 = re.match(
            r'^([A-Za-z][A-Za-z .\'()-]+),\s*([A-Z]{2})$',
            seg
        )
        if m2:
            city_part = m2.group(1).strip()
            # Filter out credential combos and name+credential patterns
            # Real city names don't end with uppercase credential words
            if (not re.match(r'^[A-Z]{2,5}$', city_part) and
                    not re.search(r'\b[A-Z]{2,5}$', city_part)):
                return seg
        # "City, StateName" (full state name, no "United States")
        m3 = re.match(
            r'^([A-Za-z][A-Za-z .\'()-]+),\s*([A-Za-z][A-Za-z ]+?)$',
            seg
        )
        if m3:
            state_part = m3.group(2).strip()
            if state_part.lower() in US_STATES:
                return seg

    # Fallback: try embedded location from full text
    if embedded:
        loc = embedded.group(1).strip()
        # Verify state part
        parts = loc.split(',')
        if len(parts) >= 2:
            state_part = parts[-2].strip() if 'United States' in parts[-1] else parts[-1].strip()
            if state_part.lower() in US_STATES:
                return loc

    return ''


def extract_li_title_from_header(header_line):
    """
    Extract the job title from a Google search result header line.
    Format: "Name - Title at Company..."
    Returns title or empty string.
    Only extracts when " at " is present (otherwise after-dash is typically a company).
    """
    m = LI_HEADER_LINE.match(header_line)
    if not m:
        return ''
    after_dash = m.group(2).strip()
    # Remove trailing "..." ellipsis
    after_dash = re.sub(r'\s*\.{3}\s*$', '', after_dash)
    # Extract title: everything before " at " (case-insensitive)
    title_match = re.match(r'^(.+?)\s+at\s+', after_dash, re.IGNORECASE)
    if title_match:
        return title_match.group(1).strip()
    # If no " at ", check if it looks like a standalone title (not a company or credentials)
    # Companies: "The University of Vermont", "HCA Florida Ocala Hospital"
    # Credentials only: "BSN, RN", "MSN, BSN, RN"
    lower = after_dash.lower()
    # Skip company names
    if lower.startswith('the ') or any(kw in lower for kw in LI_COMPANY_KEYWORDS):
        return ''
    # Skip pure credential strings (e.g., "BSN, RN", "MSN, BSN, RN")
    cred_test = re.sub(r'[,\s]+', ' ', after_dash).strip()
    cred_words = cred_test.split()
    cred_set = {'bs', 'bsn', 'msn', 'mba', 'rn', 'lpn', 'md', 'do', 'np', 'phd',
                'ms', 'ma', 'ba', 'aprn', 'fnp', 'cna', 'dnp', 'crnp', 'pa',
                'pharmd', 'dds', 'dmd', 'od', 'dc', 'dpt', 'mph', 'mha'}
    if all(w.lower().rstrip('.') in cred_set for w in cred_words):
        return ''
    # Check if it has title keywords
    if any(kw in lower for kw in LI_TITLE_KEYWORDS):
        return after_dash.strip()
    return after_dash.strip()


def extract_li_title_from_segments(segments_line):
    """
    Extract job title from the middle-dot-separated info line.
    The info line looks like:
    "City, State, United States · Title · Company"
    or "Title · Company"
    Returns title or empty string.
    """
    segments = re.split(r'\s*[·•]\s*', segments_line)
    for seg in segments:
        seg = seg.strip().rstrip('.')
        # Skip location-like segments
        if re.match(r'^[A-Za-z][A-Za-z .\'()-]+,\s*[A-Za-z]', seg):
            continue
        # Skip segments that look like company names (contain "University",
        # "Hospital", "Center", "Health", etc.)
        # But first check if it's a title — titles often have "Nurse", "Dentist", etc.
        if seg and not re.search(r'^\d', seg):
            return seg
    return ''


def is_li_next_profile(lines, i):
    """Check if line i starts a new LinkedIn profile (header + LinkedIn · line)."""
    if i >= len(lines):
        return False
    line = lines[i].strip()
    # Direct LinkedIn · line
    if LI_PROFILE_LINE.match(line):
        return True
    # Header line followed by LinkedIn · line
    if ' - ' in line:
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and LI_PROFILE_LINE.match(lines[j].strip()):
            return True
    return False


LI_COMPANY_KEYWORDS = ['university', 'hospital', 'health', 'center', 'network',
                       'medical', 'college', 'institute', 'clinic', 'corp',
                       'inc', 'llc', 'group', 'associates', 'foundation',
                       'healthcare', 'graphic', 'community']

# Title keywords — segments containing these are likely job titles
LI_TITLE_KEYWORDS = ['nurse', 'registered', 'dentist', 'doctor', 'physician',
                     'therapist', 'assistant', 'technician', 'manager', 'director',
                     'supervisor', 'coordinator', 'specialist', 'analyst', 'engineer',
                     'developer', 'consultant', 'administrator', 'practitioner',
                     'pharmacist', 'surgeon', 'paramedic', 'aide', 'staff',
                     'resource', 'critical care', 'med/surg', 'licensed']


def is_li_title_segment(seg):
    """Check if a segment looks like a job title rather than a company or location."""
    if not seg or len(seg) < 2:
        return False
    lower = seg.lower()
    # Skip location patterns
    if re.match(r'^[A-Za-z][A-Za-z .\'()-]+,\s*[A-Za-z]', seg):
        return False
    # Skip "United States" etc
    if lower in ('united states', 'united kingdom', 'canada'):
        return False
    # Skip metadata-like segments
    if lower.startswith('experience') or lower.startswith('education'):
        return False
    if lower.startswith('location:') or lower.startswith('view '):
        return False
    if 'connections on linkedin' in lower or 'profile on linkedin' in lower:
        return False
    if 'followers' in lower:
        return False
    # Check for company keywords
    if lower.startswith('the ') or any(kw in lower for kw in LI_COMPANY_KEYWORDS):
        # But if it also has a title keyword, it might be "Critical Care Registered Nurse"
        if any(kw in lower for kw in LI_TITLE_KEYWORDS):
            return True
        return False
    # If it has title keywords, definitely a title
    if any(kw in lower for kw in LI_TITLE_KEYWORDS):
        return True
    # Short segments that are all caps/credentials — skip
    if re.match(r'^[A-Z,.\s-]+$', seg) and len(seg) < 15:
        return False
    # Pure credential strings like "BSN, RN"
    cred_set = {'bs', 'bsn', 'msn', 'mba', 'rn', 'lpn', 'md', 'do', 'np', 'phd',
                'ms', 'ma', 'ba', 'aprn', 'fnp', 'cna', 'dnp', 'crnp', 'pa',
                'pharmd', 'dds', 'dmd', 'od', 'dc', 'dpt', 'mph', 'mha'}
    cred_words = re.sub(r'[,\s]+', ' ', seg).strip().split()
    if cred_words and all(w.lower().rstrip('.') in cred_set for w in cred_words):
        return False
    return True


def extract_li_title_from_info(segments_line):
    """
    Extract job title from the middle-dot-separated info line.
    Segments: location · title · company  OR  title · company · etc.
    Returns the first segment that looks like a title.
    """
    segments = re.split(r'\s*[·•]\s*', segments_line)
    for seg in segments:
        seg = seg.strip().rstrip('.')
        if is_li_title_segment(seg):
            return seg
    return ''


def extract_linkedin_xray(text):
    """
    Extract names, locations, and job titles from LinkedIn X-ray
    (Google search) results.

    Each profile block follows this structure:
        Name [credentials] - Title at Company...     (header — Google result title)
        LinkedIn · Name [credentials]                (attribution line)
        N+ followers                                 (follower count)
        [City, State, United States ·] Title · Company  (info line with middle dots)
        Description snippet...__Read more__          (description — skip)
    """
    lines = text.split('\n')
    people = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # --- Detect profile via "LinkedIn · Name" line ---
        li_match = LI_PROFILE_LINE.match(line)
        if li_match:
            raw_name = li_match.group(1).strip()
            name = strip_li_credentials(raw_name)

            # Look back for the header line (previous non-blank line)
            header_line = ''
            j = i - 1
            while j >= 0:
                prev = lines[j].strip()
                if prev:
                    header_line = prev
                    break
                j -= 1

            # Extract title from header line
            title = extract_li_title_from_header(header_line)

            i += 1  # move past the LinkedIn line

            # Skip followers line
            while i < len(lines):
                curr = lines[i].strip()
                if not curr:
                    i += 1
                    continue
                if LI_FOLLOWERS_LINE.match(curr):
                    i += 1
                    break
                break

            # Process remaining lines for this profile (info + description)
            location = ''
            info_processed = False
            while i < len(lines):
                curr = lines[i].strip()
                if not curr:
                    i += 1
                    continue

                # Check if next profile starts
                if is_li_next_profile(lines, i):
                    break

                # First non-blank line after followers is the INFO line
                # (has middle dots with location/title/company)
                if not info_processed:
                    info_processed = True
                    # Extract location from info line
                    if not location:
                        loc = extract_li_location(curr)
                        if loc:
                            location = loc
                    # Extract title from info line segments
                    if not title and ('·' in curr or '•' in curr):
                        title = extract_li_title_from_info(curr)
                    # Also handle info lines that are just "Title at Company"
                    if not title:
                        t_match = re.match(r'^(.+?)\s+at\s+', curr, re.IGNORECASE)
                        if t_match:
                            candidate = t_match.group(1).strip()
                            # Make sure it's not "Name. Title at Company" format
                            # by checking if it starts with the person's name
                            if not candidate.lower().startswith(name.split()[0].lower()):
                                title = candidate
                    i += 1
                    continue

                # Subsequent lines are description/snippets
                # Try to extract location from description if we still don't have one
                if not location:
                    loc = extract_li_location(curr)
                    if loc:
                        location = loc

                i += 1

            # Clean up title — remove trailing ellipsis
            if title:
                title = re.sub(r'\s*\.{3}\s*$', '', title).strip()

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
