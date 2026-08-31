import argparse
import json
import os
import sys
from pathlib import Path
from .indexer import MinerUIndexer

def main():
    parser = argparse.ArgumentParser(description="Generate Eduteria Content Index from MinerU output")
    parser.add_argument("--mineru-output", required=True, help="Path to MinerU output directory")
    parser.add_argument("--source-pdf", required=True, help="Path to original PDF file")
    parser.add_argument("--book-id", default="NCERT-TEST-01", help="Book identifier")
    parser.add_argument("--parser-version", default="0.1.0", help="MinerU parser version")
    
    args = parser.parse_args()
    
    output_dir = Path(args.mineru_output)
    pdf_stem = Path(args.source_pdf).stem
    
    v2_path = output_dir / f"{pdf_stem}_content_list_v2.json"
    middle_path = output_dir / f"{pdf_stem}_middle.json"
    
    if not v2_path.exists() or not middle_path.exists():
        print(f"Error: Missing MinerU output files in {output_dir}")
        sys.exit(1)
        
    print(f"Loading MinerU output from {output_dir}...")
    with open(v2_path, 'r', encoding='utf-8') as f:
        v2_data = json.load(f)
    with open(middle_path, 'r', encoding='utf-8') as f:
        middle_data = json.load(f)
        
    book_config = {
        "id": args.book_id,
        "title": "Test Book",
        "subject": "Chemistry",
        "class_level": "12",
        "publisher": "NCERT",
        "language": "en"
    }
    
    print("Generating Eduteria Content Index...")
    indexer = MinerUIndexer(str(output_dir), book_config)
    indexer.generate_index(v2_data, middle_data, args.source_pdf, args.parser_version)
    
    print(f"Index generated at: {indexer.index_dir}")

if __name__ == "__main__":
    main()
