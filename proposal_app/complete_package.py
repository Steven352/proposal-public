from .github_library import GitHubLibrary, save_pdf_source_to_library
from .models import ProposalFacts
from .pdf_builder import build_complete_pdf_package
from .uploaded_proposal import client_email_from_proposal


def generate_complete_package(
    word: bytes, filename: str, facts: ProposalFacts, scope: str, budget: float,
    add_signatures: bool, library: GitHubLibrary | None, *, archive_source: bool = True,
) -> dict:
    prepared = word  # The reviewed Word is authoritative, including manual scope changes.
    pdf, name = build_complete_pdf_package(prepared, facts, scope, budget, add_signatures=add_signatures)
    subject, body = client_email_from_proposal(facts)
    result = {
        'pdf': pdf, 'name': name, 'word': prepared, 'word_changed': prepared != word,
        'signed': add_signatures, 'email_subject': subject, 'email_body': body,
        'library_error': '', 'library_path': '',
    }
    if not archive_source:
        return result

    try:
        if library is None:
            raise RuntimeError('Private library storage is not configured. Set GITHUB_LIBRARY_TOKEN and GITHUB_LIBRARY_REPO in Streamlit Secrets.')
        _, state, path = save_pdf_source_to_library(library, filename, word)
        result.update(library_state=state, library_path=path)
    except Exception as error:
        result['library_error'] = str(error)
    return result
