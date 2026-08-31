from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class MinerUSource(BaseModel):
    file: str  # e.g. "test_content_list_v2.json"
    page_index: int
    block_index: int
    block_type: str
    content_fingerprint: str  # A hash of canonical text to verify block identity

class ContentBlockReference(BaseModel):
    id: str
    type: Literal['heading', 'paragraph', 'list', 'list_item', 'equation', 'table', 'image', 'caption']
    order: int
    mineru_source: MinerUSource

class Page(BaseModel):
    id: str
    chapter_id: str
    page_number: int  # 1-indexed
    mineru_page_index: int  # 0-indexed
    dimensions: Optional[List[float]] = None  # [width, height]
    bbox_coordinate_system: str = "mineru_v2_normalized_1000x1000"
    blocks: List[ContentBlockReference] = Field(default_factory=list)

class Chapter(BaseModel):
    id: str
    number: Optional[int] = None
    title: str
    order: int

class Book(BaseModel):
    id: str
    title: Optional[str] = None
    subject: Optional[str] = None
    class_level: Optional[str] = None
    publisher: Optional[str] = None
    language: Optional[str] = None

class SourceManifest(BaseModel):
    source_file: str
    source_hash: str
    parser_name: str
    parser_version: str

class EduteriaContentIndex(BaseModel):
    schema_version: str
    content_version: str
    generated_at: str
    source: SourceManifest
    book: Book
    chapters: List[Chapter]
    pages: List[Page]
