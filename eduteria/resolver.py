import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

class ContentResolver:
    """
    Resolves Eduteria Content Index IDs back to their rich MinerU source blocks.
    """
    def __init__(self, index_dir: str, mineru_output_dir: str):
        self.index_dir = Path(index_dir)
        self.mineru_dir = Path(mineru_output_dir)
        self.pages_dir = self.index_dir / "pages"
        
        # Caches
        self.pages_cache = {}
        self.v2_cache = None
        
    def _load_v2_data(self) -> list:
        if self.v2_cache is None:
            v2_path = self.mineru_dir / "test_content_list_v2.json"
            with open(v2_path, "r", encoding="utf-8") as f:
                self.v2_cache = json.load(f)
        return self.v2_cache

    def resolve_content(self, eduteria_id: str) -> Optional[Dict[str, Any]]:
        """
        Resolves a stable Eduteria block ID to the original MinerU block.
        Returns the original MinerU block dictionary.
        """
        # 1. We don't have a direct ID->Page mapping without scanning or using the page number encoded in the ID.
        # ID format: {chapter_id}-p{page_number:04d}-{content_hash}
        try:
            parts = eduteria_id.split("-p")
            page_part = parts[1].split("-")[0]
            page_number = int(page_part)
        except Exception:
            raise ValueError(f"Invalid Eduteria ID format: {eduteria_id}")
            
        page_file = self.pages_dir / f"page-{page_number:04d}.json"
        if not page_file.exists():
            return None
            
        if page_number not in self.pages_cache:
            with open(page_file, "r", encoding="utf-8") as f:
                self.pages_cache[page_number] = json.load(f)
                
        page_data = self.pages_cache[page_number]
        
        # 2. Find block in page
        target_block = None
        for block in page_data.get("blocks", []):
            if block["id"] == eduteria_id:
                target_block = block
                break
                
        if not target_block:
            return None
            
        # 3. Use mineru_source to locate original data
        source_ref = target_block["mineru_source"]
        # We assume file is "test_content_list_v2.json" for now
        v2_data = self._load_v2_data()
        
        page_idx = source_ref["page_index"]
        block_idx = source_ref["block_index"]
        
        if page_idx >= len(v2_data):
            return None
            
        page_blocks = v2_data[page_idx]
        if block_idx >= len(page_blocks):
            return None
            
        mineru_block = page_blocks[block_idx]
        
        # 4. Verify identity using block_type (and we could verify fingerprint here)
        if mineru_block.get("type") != source_ref["block_type"]:
            raise RuntimeError(f"Identity mismatch: expected {source_ref['block_type']} but got {mineru_block.get('type')}")
            
        return mineru_block
