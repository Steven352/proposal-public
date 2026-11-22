"""Format supplied Canadian addresses without inventing missing address components."""
import re


PROVINCES = {
    'AB': 'Alberta', 'BC': 'British Columbia', 'MB': 'Manitoba',
    'NB': 'New Brunswick', 'NL': 'Newfoundland and Labrador', 'NS': 'Nova Scotia',
    'NT': 'Northwest Territories', 'NU': 'Nunavut', 'ON': 'Ontario',
    'PE': 'Prince Edward Island', 'QC': 'Quebec', 'SK': 'Saskatchewan', 'YT': 'Yukon',
}
POSTAL = re.compile(r'\b([A-Z]\d[A-Z])\s*(\d[A-Z]\d)\b', re.I)
PROVINCE = re.compile(r'^(.*?)\b(' + '|'.join([*PROVINCES, *PROVINCES.values()]) + r')\.?$', re.I)


def format_address(value: str) -> str:
    # Commas inside legal land descriptions belong to the street/location line.
    parts = [part.strip(' ,\t\r') for part in re.split(r'\n|,(?![^()]*\))', value) if part.strip(' ,\t\r')]
    lines = []
    postals = []
    for part in parts:
        for match in POSTAL.finditer(part):
            postal = (match[1] + ' ' + match[2]).upper()
            if postal not in postals:
                postals.append(postal)
        part = POSTAL.sub('', part).strip(' ,')
        if not part:
            continue
        match = PROVINCE.fullmatch(part)
        if match:
            city = match[1].strip(' ,')
            province = PROVINCES.get(match[2].upper(), match[2])
            if not city and lines:
                city = lines.pop()
            part = f'{city}, {province}' if city else province
        if not lines or lines[-1].casefold() != part.casefold():
            lines.append(part)
    return '\n'.join([*lines, *postals])


def project_address(name: str, location: str) -> str:
    lines = format_address(location).splitlines()
    name = name.strip()
    if not lines:
        return format_address(name)
    # Retain a supplied legal description on the address without duplicating the street.
    name_street = name.split('(', 1)[0].strip()
    first_street = lines[0].split('(', 1)[0].strip()
    if name_street.casefold() == first_street.casefold():
        if '(' in name and '(' not in lines[0]:
            lines[0] = name
    elif not re.search(r'\d', lines[0]) and name:
        lines.insert(0, name)
    return '\n'.join(lines)
