import unicodedata
import hashlib

def normalize_text(text: str) -> str:
    """
    Normalizes text for determinism:
    1. Unicode NFKC normalization
    2. Strips leading/trailing whitespace
    """
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text).strip()

def generate_block_id(
    book_id: str,
    chapter_id: str,
    page_index: int,
    block_type: str,
    canonical_text: str,
    occurrence_index: int
) -> str:
    """
    Generates a stable, deterministic ID for a content block.
    
    The ID is constructed as:
    {chapter_id}-p{page_number:04d}-{content_hash}
    
    where content_hash is a short SHA-256 hash derived from:
    - book_id
    - chapter_id
    - page_index
    - block_type
    - canonical_text (normalized)
    - occurrence_index (to handle exact duplicates on the same page)
    """
    page_number = page_index + 1
    
    # Core identity components
    components = [
        book_id,
        chapter_id,
        str(page_index),
        block_type,
        normalize_text(canonical_text),
        str(occurrence_index)
    ]
    
    identity_string = "||".join(components)
    
    # Hash the identity string (first 12 chars is plenty for collision resistance within a page)
    content_hash = hashlib.sha256(identity_string.encode('utf-8')).hexdigest()[:17]
    
    return f"{chapter_id}-p{page_number:04d}-b{content_hash}"

def generate_fingerprint(canonical_text: str) -> str:
    """
    Generates a short fingerprint of the canonical text to verify block identity
    during resolution.
    """
    if not canonical_text:
        return "empty"
    return hashlib.sha256(normalize_text(canonical_text).encode('utf-8')).hexdigest()[:12]
