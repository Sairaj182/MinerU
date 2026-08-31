import json
from pathlib import Path
from typing import List, Tuple
from .schema import EduteriaContentIndex, SourceManifest, Book, Chapter, Page
from .resolver import ContentResolver
from .normalizer import generate_fingerprint

def validate_index(index_dir: str, mineru_dir: str) -> Tuple[bool, List[str]]:
    """
    Validates the Eduteria Content Index and its relation to the MinerU source.
    """
    base_dir = Path(index_dir)
    messages = []
    is_valid = True

    try:
        # 1. Manifest
        manifest_path = base_dir / "manifest.json"
        if not manifest_path.exists():
            messages.append("ERROR: manifest.json missing")
            is_valid = False
        else:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                SourceManifest.model_validate_json(f.read())
                
        # 2. Book
        book_path = base_dir / "book.json"
        if not book_path.exists():
            messages.append("ERROR: book.json missing")
            is_valid = False
        else:
            with open(book_path, 'r', encoding='utf-8') as f:
                Book.model_validate_json(f.read())
                
        # 3. Chapters
        chapters_path = base_dir / "chapters.json"
        if not chapters_path.exists():
            messages.append("ERROR: chapters.json missing")
            is_valid = False
        else:
            with open(chapters_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for c in data.get("chapters", []):
                    Chapter.model_validate(c)
                    
        # 4. Pages & Highlight Resolution
        pages_dir = base_dir / "pages"
        if not pages_dir.exists():
            messages.append("ERROR: pages directory missing")
            is_valid = False
        else:
            page_files = list(pages_dir.glob("page-*.json"))
            if not page_files:
                messages.append("WARNING: No page files found")
                
            resolver = ContentResolver(index_dir, mineru_dir)
            
            # For verifying ID uniqueness
            all_block_ids = set()
            
            # Temporary indexer instance just to reuse text extraction logic for validation
            from .indexer import MinerUIndexer
            tmp_indexer = MinerUIndexer(".", {})
            
            for page_file in page_files:
                with open(page_file, 'r', encoding='utf-8') as f:
                    page = Page.model_validate_json(f.read())
                    
                    for block in page.blocks:
                        # Check ID uniqueness
                        if block.id in all_block_ids:
                            messages.append(f"ERROR: Duplicate ID found: {block.id}")
                            is_valid = False
                        all_block_ids.add(block.id)
                        
                        # Test Highlight Resolution
                        # Resolve the block
                        mineru_block = resolver.resolve_content(block.id)
                        if not mineru_block:
                            messages.append(f"ERROR: Could not resolve source for block {block.id}")
                            is_valid = False
                            continue
                            
                        # Re-extract text and verify fingerprint
                        raw_type = block.mineru_source.block_type
                        content = mineru_block.get("content", {})
                        canonical_text = tmp_indexer._extract_canonical_text(content, raw_type)
                        
                        expected_fingerprint = block.mineru_source.content_fingerprint
                        actual_fingerprint = generate_fingerprint(canonical_text)
                        
                        if expected_fingerprint != actual_fingerprint:
                            messages.append(f"ERROR: Fingerprint mismatch for {block.id}. Expected {expected_fingerprint}, got {actual_fingerprint}")
                            is_valid = False
                            
    except Exception as e:
        messages.append(f"ERROR: Validation exception: {str(e)}")
        is_valid = False

    return is_valid, messages

if __name__ == "__main__":
    import sys
    idx_dir = sys.argv[1]
    src_dir = sys.argv[2]
    valid, msgs = validate_index(idx_dir, src_dir)
    for m in msgs:
        print(m)
    if valid:
        print("[SUCCESS] Validation successful!")
        sys.exit(0)
    else:
        print("[FAILED] Validation failed.")
        sys.exit(1)
