import re
from urllib.parse import unquote


def parse_identifier(value):
    value = unquote(value.strip())
    value = re.sub(r'^https?://(?:dx\.)?doi.org/', '', value, flags=re.I)
    value = re.sub(r'^doi:\s*', '', value, flags=re.I)
    if re.fullmatch(r'10\.\d{4,9}/\S+', value):
        return 'doi', value.lower()
    pmid = re.sub(r'^(?:https?://pubmed.ncbi.nlm.nih.gov/|pmid:\s*)', '', value, flags=re.I).rstrip('/')
    if re.fullmatch(r'[1-9]\d*', pmid):
        return 'pmid', pmid
    work = re.sub(r'^https?://openalex.org/', '', value, flags=re.I)
    if re.fullmatch(r'W\d+', work, re.I):
        return 'openalex', work.upper()
    raise ValueError('Enter a DOI, PMID, or OpenAlex Work ID.')
