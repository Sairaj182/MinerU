import argparse
import os
import sys
import subprocess
import logging
from pathlib import Path
import re
import traceback
import shutil

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def generate_book_id(input_dir: Path, pdf_path: Path) -> str:
    rel_path = pdf_path.relative_to(input_dir)
    parts = list(rel_path.parts[:-1]) + [rel_path.stem]
    book_id = "-".join(parts)
    book_id = re.sub(r'[^a-zA-Z0-9_\-]', '-', book_id).lower()
    return book_id

def find_mineru_output(base_dir: Path, pdf_stem: str) -> Path:
    """Finds the actual directory containing the MinerU json output."""
    target_file = f"{pdf_stem}_content_list_v2.json"
    for path in base_dir.rglob(target_file):
        return path.parent
    return None

def main():
    parser = argparse.ArgumentParser(description="Bulk process PDFs with MinerU and Eduteria Indexer")
    parser.add_argument("--input-dir", required=True, help="Root directory containing PDFs")
    parser.add_argument("--output-dir", required=True, help="Root directory where processed books will be stored")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)

    pdfs = list(input_dir.rglob("*.pdf"))
    total_books = len(pdfs)
    
    if total_books == 0:
        logger.warning(f"No PDFs found in {input_dir}")
        sys.exit(0)

    logger.info(f"Found {total_books} PDFs for processing.")

    results = {
        "successful": [],
        "failed": [],
        "skipped": []
    }

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    for idx, pdf_path in enumerate(pdfs, 1):
        try:
            logger.info(f"[{idx}/{total_books}] Processing {pdf_path.relative_to(input_dir)}")
            
            book_id = generate_book_id(input_dir, pdf_path)
            pdf_stem = pdf_path.stem

            rel_path = pdf_path.relative_to(input_dir)
            book_output_dir = output_dir / rel_path.parent / pdf_stem
            book_output_dir.mkdir(parents=True, exist_ok=True)

            mineru_out_dir = book_output_dir / "mineru"
            eduteria_out_dir = book_output_dir / "eduteria"

            # Check Resumability
            mineru_done = False
            actual_mineru_out = find_mineru_output(mineru_out_dir, pdf_stem)
            if actual_mineru_out and (actual_mineru_out / f"{pdf_stem}_middle.json").exists():
                mineru_done = True

            eduteria_done = False
            if eduteria_out_dir.exists() and (eduteria_out_dir / "book.json").exists():
                eduteria_done = True

            if mineru_done and eduteria_done:
                logger.info(f"[{idx}/{total_books}] MinerU: SKIPPED (already complete)")
                logger.info(f"[{idx}/{total_books}] Eduteria: SKIPPED (already complete)")
                logger.info(f"[{idx}/{total_books}] Book: COMPLETE")
                results["skipped"].append(str(pdf_path))
                continue

            # 1. Run MinerU
            if not mineru_done:
                logger.info(f"[{idx}/{total_books}] MinerU: START")
                cmd = [
                    sys.executable, "-m", "mineru.cli.client",
                    "-p", str(pdf_path),
                    "-o", str(mineru_out_dir),
                    "-m", "auto",
                    "-b", "hybrid-engine",
                    "--effort", "high",
                    "-f", "True",
                    "-t", "True",
                    "--image-analysis", "True",
                    "--client-side-output-generation", "True",
                    "-l", "ch"
                ]
                subprocess.run(cmd, check=True, env=env)
                logger.info(f"[{idx}/{total_books}] MinerU: SUCCESS")
                
                # Re-evaluate actual_mineru_out after run
                actual_mineru_out = find_mineru_output(mineru_out_dir, pdf_stem)
                if not actual_mineru_out:
                    raise FileNotFoundError(f"MinerU output files not found in {mineru_out_dir} after successful run")
            else:
                logger.info(f"[{idx}/{total_books}] MinerU: SKIPPED (already complete)")

            # 2. Run Eduteria Indexer
            if not eduteria_done:
                logger.info(f"[{idx}/{total_books}] Eduteria indexer: START")
                eduteria_cmd = [
                    sys.executable, "-m", "eduteria.cli",
                    "--mineru-output", str(actual_mineru_out),
                    "--source-pdf", str(pdf_path),
                    "--book-id", book_id
                ]
                subprocess.run(eduteria_cmd, check=True, env=env)
                
                generated_index_dir = actual_mineru_out / "eduteria_index"
                if generated_index_dir.exists():
                    if eduteria_out_dir.exists():
                        shutil.rmtree(eduteria_out_dir)
                    shutil.copytree(generated_index_dir, eduteria_out_dir)
                else:
                    raise FileNotFoundError(f"Eduteria index not found at {generated_index_dir}")

                logger.info(f"[{idx}/{total_books}] Eduteria indexer: SUCCESS")
            else:
                logger.info(f"[{idx}/{total_books}] Eduteria indexer: SKIPPED (already complete)")

            logger.info(f"[{idx}/{total_books}] Book: COMPLETE")
            results["successful"].append(str(pdf_path))

        except Exception as e:
            logger.error(f"[{idx}/{total_books}] Processing failed: {e}")
            logger.debug(traceback.format_exc())
            results["failed"].append(str(pdf_path))
            continue

    print("\n========================================")
    print("Bulk Processing Complete")
    print("========================================")
    print(f"Total books:     {total_books}")
    print(f"Successful:      {len(results['successful'])}")
    print(f"Failed:          {len(results['failed'])}")
    print(f"Skipped:         {len(results['skipped'])}")

    if results['failed']:
        print("\nFailed books:")
        for f in results['failed']:
            print(f"- {Path(f).relative_to(input_dir)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
