import json
import os
from typing import List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import hashlib

from .schema import (
    SourceManifest, Book, Chapter, Page, ContentBlockReference, MinerUSource, EduteriaContentIndex
)
from .normalizer import normalize_text, generate_block_id, generate_fingerprint

class MinerUIndexer:
    def __init__(self, output_dir: str, book_config: Dict[str, Any]):
        self.output_dir = Path(output_dir)
        self.index_dir = self.output_dir / "eduteria_index"
        self.pages_dir = self.index_dir / "pages"
        self.book_config = book_config
        self.book_id = book_config.get("id", "book-default")
        
        self.current_chapter_idx = 1
        self.chapters: List[Chapter] = []
        self.pages: List[Page] = []
        
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    def _extract_canonical_text(self, content: Dict[str, Any], block_type: str) -> str:
        """Dynamically computes canonical text to generate deterministic IDs and fingerprints.
        This text is NOT stored in the index."""
        if block_type == "title":
            parts = content.get("title_content", [])
        elif block_type == "paragraph":
            parts = content.get("paragraph_content", [])
        elif block_type == "list":
            items = content.get("list_items", [])
            all_canonical = []
            for item in items:
                item_canonical_parts = []
                for ic in item.get("item_content", []):
                    if ic.get("type") == "text":
                        item_canonical_parts.append(ic.get("content", ""))
                    elif ic.get("type") == "equation_inline":
                        eq = ic.get("content", "")
                        item_canonical_parts.append(f"${eq}$")
                all_canonical.append(normalize_text("".join(item_canonical_parts)))
            return " | ".join(all_canonical)
        elif block_type in ["page_footer", "page_number"]:
            parts = content.get(f"{block_type}_content", [])
            return "".join(p.get("content", "") for p in parts)
        elif block_type == "image":
            return content.get("content", "")
        elif block_type == "equation":
            return content.get("math_content", "")
        else:
            return ""

        canonical_texts = []
        for part in parts:
            if part.get("type") == "text":
                canonical_texts.append(part.get("content", ""))
            elif part.get("type") == "equation_inline":
                eq = part.get("content", "")
                canonical_texts.append(f"${eq}$")
                
        return "".join(canonical_texts)

    def _map_block_type(self, mineru_type: str) -> str:
        mapping = {
            "title": "heading",
            "paragraph": "paragraph",
            "list": "list",
            "table": "table",
            "image": "image",
            "equation_interline": "equation",
            "equation_inline": "equation",
            "equation": "equation",
            "page_footer": "caption",
            "page_number": "caption",
            "text": "paragraph"
        }
        return mapping.get(mineru_type, "paragraph")

    def generate_index(self, v2_data: List[List[Dict[str, Any]]], middle_data: Dict[str, Any], source_pdf: str, parser_version: str):
        # We start at 0. If the first page has no L1 titles, it will use ch00 (Frontmatter)
        self.current_chapter_idx = 0
        frontmatter_created = False

        # Extract page dimensions from middle_data
        page_dimensions = {}
        for p in middle_data.get("pdf_info", []):
            idx = p.get("page_idx")
            size = p.get("page_size")
            if idx is not None and size is not None:
                page_dimensions[idx] = size

        for page_idx, page_blocks in enumerate(v2_data):
            page_number = page_idx + 1
            blocks: List[ContentBlockReference] = []
            
            # Find level 1 titles on this page
            l1_titles = []
            for b in page_blocks:
                if b.get("type") == "title" and b.get("content", {}).get("level") == 1:
                    canonical_text = self._extract_canonical_text(b.get("content", {}), b.get("type"))
                    l1_titles.append(normalize_text(canonical_text))
            
            if l1_titles:
                self.current_chapter_idx += 1
                page_chapter_id = f"ch{self.current_chapter_idx:02d}"
                self.chapters.append(Chapter(
                    id=page_chapter_id,
                    number=self.current_chapter_idx,
                    title=" - ".join(l1_titles)[:100],
                    order=self.current_chapter_idx
                ))
            else:
                page_chapter_id = f"ch{self.current_chapter_idx:02d}"
                if self.current_chapter_idx == 0 and not frontmatter_created:
                    # Create implicit Frontmatter chapter
                    self.chapters.append(Chapter(
                        id=page_chapter_id,
                        number=0,
                        title="Frontmatter",
                        order=0
                    ))
                    frontmatter_created = True
            
            text_occurrences = {}
            
            for block_order, block in enumerate(page_blocks):
                b_type_raw = block.get("type", "unknown")
                b_type = self._map_block_type(b_type_raw)
                content = block.get("content", {})
                
                # Extract canonical text for hashing ONLY
                canonical_text = self._extract_canonical_text(content, b_type_raw)
                canonical_text_norm = normalize_text(canonical_text)
                fingerprint = generate_fingerprint(canonical_text_norm)
                
                occurrence_key = f"{b_type}:{canonical_text_norm}"
                occurrence = text_occurrences.get(occurrence_key, 0)
                text_occurrences[occurrence_key] = occurrence + 1
                
                block_id = generate_block_id(
                    book_id=self.book_id,
                    chapter_id=page_chapter_id,
                    page_index=page_idx,
                    block_type=b_type,
                    canonical_text=canonical_text_norm,
                    occurrence_index=occurrence
                )
                
                pdf_stem = Path(source_pdf).stem
                source_ref = MinerUSource(
                    file=f"{pdf_stem}_content_list_v2.json",
                    page_index=page_idx,
                    block_index=block_order,
                    block_type=b_type_raw,
                    content_fingerprint=fingerprint
                )
                
                cb = ContentBlockReference(
                    id=block_id,
                    type=b_type,
                    order=block_order + 1,
                    mineru_source=source_ref
                )
                blocks.append(cb)
                
            p_dim = page_dimensions.get(page_idx, [576.0, 784.0])
            
            page = Page(
                id=f"{self.book_id}-p{page_number:04d}",
                chapter_id=page_chapter_id,
                page_number=page_number,
                mineru_page_index=page_idx,
                dimensions=p_dim,
                blocks=blocks
            )
            self.pages.append(page)
            
        self._write_index(source_pdf, parser_version)

    def _write_index(self, source_pdf: str, parser_version: str):
        source_hash = "unknown"
        if os.path.exists(source_pdf):
            sha256_hash = hashlib.sha256()
            with open(source_pdf, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            source_hash = sha256_hash.hexdigest()

        manifest = SourceManifest(
            source_file=os.path.basename(source_pdf),
            source_hash=source_hash,
            parser_name="MinerU",
            parser_version=parser_version
        )
        
        book = Book(**self.book_config)
        
        index = EduteriaContentIndex(
            schema_version="2.0",
            content_version="1.0",
            generated_at=datetime.utcnow().isoformat() + "Z",
            source=manifest,
            book=book,
            chapters=self.chapters,
            pages=[] # Exclude pages from the root index file for modularity
        )
        
        # Write root components
        with open(self.index_dir / "manifest.json", "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2))
            
        with open(self.index_dir / "book.json", "w", encoding="utf-8") as f:
            f.write(book.model_dump_json(indent=2))
            
        with open(self.index_dir / "chapters.json", "w", encoding="utf-8") as f:
            json.dump({"chapters": [c.model_dump() for c in self.chapters]}, f, indent=2)
            
        # Write page-level files
        for page in self.pages:
            page_file = self.pages_dir / f"page-{page.page_number:04d}.json"
            with open(page_file, "w", encoding="utf-8") as f:
                f.write(page.model_dump_json(indent=2))
