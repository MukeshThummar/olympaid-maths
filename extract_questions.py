#!/usr/bin/env python3
"""
Maths Olympiad PDF Question Extractor
======================================
Extracts MCQ questions, options (A/B/C/D or P/Q/R/S), correct answers,
hints, explanations, and images (as Base64) from the PDF workbook.

Output:
  - questions.json   : All extracted questions with Base64 images
  - extraction_report.txt : Summary of extraction results
"""

import re
import json
import base64
import io
import os
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("ERROR: pdfplumber not installed. Run: pip install pdfplumber")

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("ERROR: pymupdf not installed. Run: pip install pymupdf")

try:
    from PIL import Image
except ImportError:
    sys.exit("ERROR: Pillow not installed. Run: pip install pillow")

# ─────────────────────────────────────────────────────────────────────────────
PDF_PATH = Path("docs/Maths Olympiad workbook.pdf")
OUTPUT_JSON = Path("questions.json")
REPORT_PATH = Path("extraction_report.txt")
IMAGE_DPI = 180          # DPI for rendering page crops (higher = clearer)
MIN_IMAGE_AREA = 5000    # Minimum pixel area to consider an image relevant
# ─────────────────────────────────────────────────────────────────────────────


def log(msg):
    print(msg, flush=True)


# ──────────────────────────────────────────────────────────────────────────────
# TEXT CLEANING
# ──────────────────────────────────────────────────────────────────────────────
def clean(text: str) -> str:
    """Remove excessive whitespace and normalize unicode dashes."""
    if not text:
        return ""
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ──────────────────────────────────────────────────────────────────────────────
# IMAGE EXTRACTION  (PyMuPDF)
# ──────────────────────────────────────────────────────────────────────────────
def page_to_pil(doc: fitz.Document, page_num: int, clip_rect=None) -> Image.Image:
    """Render a page (or region) to a PIL Image."""
    page = doc[page_num]
    mat = fitz.Matrix(IMAGE_DPI / 72, IMAGE_DPI / 72)
    if clip_rect:
        clip = fitz.Rect(clip_rect)
        pix = page.get_pixmap(matrix=mat, clip=clip)
    else:
        pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


def pil_to_base64(img: Image.Image) -> str:
    """Convert PIL Image to Base64 PNG string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def get_embedded_images_on_page(doc: fitz.Document, page_num: int):
    """
    Return list of (x0, y0, x1, y1, base64_str) for every embedded
    raster image on the page that's large enough to be meaningful.
    """
    page = doc[page_num]
    results = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        try:
            base_img = doc.extract_image(xref)
            img_bytes = base_img["image"]
            img = Image.open(io.BytesIO(img_bytes))
            w, h = img.size
            if w * h < MIN_IMAGE_AREA:
                continue
            b64 = "data:image/png;base64," + base64.b64encode(img_bytes).decode()
            # Find bounding box on page
            rects = page.get_image_rects(xref)
            for rect in rects:
                results.append((rect.x0, rect.y0, rect.x1, rect.y1, b64, w, h))
        except Exception:
            continue
    return results


# ──────────────────────────────────────────────────────────────────────────────
# PDF STRUCTURE SCANNER  (first pass — figure out layout)
# ──────────────────────────────────────────────────────────────────────────────
def scan_structure(pdf_path: Path):
    """Print the first 8 pages of raw text so we can understand the layout."""
    log("\n=== STRUCTURE SCAN (first 8 pages) ===\n")
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages[:8]):
            text = page.extract_text() or ""
            log(f"--- PAGE {i+1} ---")
            log(text[:2000])
            log("")


# ──────────────────────────────────────────────────────────────────────────────
# FULL TEXT EXTRACTION  (pdfplumber)
# ──────────────────────────────────────────────────────────────────────────────
def extract_full_text(pdf_path: Path):
    """
    Extract text page-by-page, preserving page numbers for later
    image correlation.
    Returns list of (page_num_0indexed, text)
    """
    pages_text = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        log(f"Total pages: {total}")
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages_text.append((i, text))
            if (i + 1) % 20 == 0:
                log(f"  Read {i+1}/{total} pages…")
    return pages_text


# ──────────────────────────────────────────────────────────────────────────────
# CHAPTER DETECTION
# ──────────────────────────────────────────────────────────────────────────────
CHAPTER_PATTERNS = [
    re.compile(r"^(Chapter\s+\d+[\s\-:]+.+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(CHAPTER\s+\d+[\s\-:]+.+)$", re.MULTILINE),
    re.compile(r"^(Unit\s+\d+[\s\-:]+.+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(Section\s+\d+[\s\-:]+.+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(PART\s+[A-Z0-9]+[\s\-:]+.+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(Topic\s*[\d:]+.+)$", re.IGNORECASE | re.MULTILINE),
]

def detect_chapter(text: str) -> str | None:
    for pat in CHAPTER_PATTERNS:
        m = pat.search(text)
        if m:
            return clean(m.group(1))
    return None


# ──────────────────────────────────────────────────────────────────────────────
# QUESTION BLOCK PARSER
# ──────────────────────────────────────────────────────────────────────────────

# Matches: "1.", "Q1.", "Q.1", "1)", "(1)" at start of line
Q_START = re.compile(
    r"^(?:Q\.?\s*)?(\d+)[.)]\s+(.+)",
    re.IGNORECASE
)

# Option line: "A." / "(A)" / "A)" / "A ." with optional text
OPT_LINE = re.compile(
    r"^\s*\(?\s*([A-EPQRSabcepqrs])\s*[).]\s*(.+)"
)

# Answer line variants
ANS_LINE = re.compile(
    r"(?:ans(?:wer)?|correct\s+answer|key)\s*[:\-]?\s*\(?([A-EPQRSabcepqrs])\)?",
    re.IGNORECASE
)

# Hint line
HINT_LINE = re.compile(r"hint\s*[:\-]?\s*(.+)", re.IGNORECASE)

# Explanation / Solution line
EXP_LINE = re.compile(
    r"(?:explanation|solution|sol\.?|exp\.?)\s*[:\-]?\s*(.+)",
    re.IGNORECASE
)


def parse_option_key(raw: str) -> str:
    """Normalize option key to uppercase."""
    return raw.strip().upper()


def is_abcd_set(keys):
    return bool(keys & {"A", "B", "C", "D"})

def is_pqrs_set(keys):
    return bool(keys & {"P", "Q", "R", "S"})


def parse_questions_from_pages(pages_text):
    """
    Multi-pass parser:
      1. Concatenate all page text keeping page-break markers.
      2. Split into question blocks.
      3. Parse each block for options, answer, hint, explanation.
    """
    # ── 1. Build mega-text with page markers ──────────────────────────────────
    full_lines = []
    for page_num, text in pages_text:
        full_lines.append(f"##PAGE:{page_num}##")
        full_lines.extend(text.splitlines())

    # ── 2. Split into question blocks ─────────────────────────────────────────
    # We'll track lines, collecting blocks between Q_START matches
    question_blocks = []   # list of (q_num, start_page, lines_list)
    current_block = None
    current_page = 0
    current_chapter = "Unknown"
    page_chapter_map = {}  # page_num -> chapter

    for raw_line in full_lines:
        # Page marker
        pm = re.match(r"##PAGE:(\d+)##", raw_line)
        if pm:
            current_page = int(pm.group(1))
            continue

        line = raw_line.rstrip()

        # Chapter detection
        ch = detect_chapter(line)
        if ch:
            current_chapter = ch
            page_chapter_map[current_page] = current_chapter

        # New question?
        qm = Q_START.match(line)
        if qm:
            if current_block is not None:
                question_blocks.append(current_block)
            q_num = int(qm.group(1))
            q_text_first = qm.group(2).strip()
            current_block = {
                "num": q_num,
                "page": current_page,
                "chapter": current_chapter,
                "lines": [q_text_first],
            }
        elif current_block is not None:
            current_block["lines"].append(line)

    if current_block is not None:
        question_blocks.append(current_block)

    log(f"  Found {len(question_blocks)} raw question blocks")

    # ── 3. Parse each block ───────────────────────────────────────────────────
    questions = []
    for block in question_blocks:
        q = parse_block(block)
        if q:
            questions.append(q)

    return questions


def parse_block(block: dict) -> dict | None:
    lines = block["lines"]
    if not lines:
        return None

    options = {}
    option_key = None
    question_lines = []
    hint_lines = []
    explanation_lines = []
    correct_answer = None

    # State machine: q_text → options → answer / hint / explanation
    state = "question"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check answer line
        am = ANS_LINE.search(stripped)
        if am:
            correct_answer = parse_option_key(am.group(1))
            # Remaining text after answer marker is explanation start
            rest = stripped[am.end():].strip()
            if rest:
                explanation_lines.append(rest)
            state = "explanation"
            continue

        # Check hint
        hm = HINT_LINE.match(stripped)
        if hm:
            hint_lines.append(hm.group(1).strip())
            state = "hint"
            continue

        # Check explanation
        em = EXP_LINE.match(stripped)
        if em:
            explanation_lines.append(em.group(1).strip())
            state = "explanation"
            continue

        # Check option line
        om = OPT_LINE.match(stripped)
        if om:
            key = parse_option_key(om.group(1))
            val = om.group(2).strip()
            # Only accept A-E or P-S as valid option keys
            if key in "ABCDEPQRS":
                options[key] = val
                option_key = key
                state = "option"
                continue

        # Continuation lines
        if state == "question":
            question_lines.append(stripped)
        elif state == "option" and option_key:
            options[option_key] = options[option_key] + " " + stripped
        elif state == "hint":
            hint_lines.append(stripped)
        elif state == "explanation":
            explanation_lines.append(stripped)
        else:
            question_lines.append(stripped)

    question_text = clean(" ".join(question_lines))
    hint_text = clean(" ".join(hint_lines))
    explanation_text = clean(" ".join(explanation_lines))

    # Determine option type
    opt_keys = set(options.keys())
    if is_pqrs_set(opt_keys):
        option_type = "PQRS"
    else:
        option_type = "ABCD"

    # Clean up option values
    cleaned_options = {k: clean(v) for k, v in options.items()}

    return {
        "id": block["num"],
        "chapter": block["chapter"],
        "page": block["page"] + 1,  # 1-indexed for human reading
        "question": question_text,
        "option_type": option_type,
        "options": cleaned_options,
        "correct_answer": correct_answer,
        "hint": hint_text,
        "explanation": explanation_text,
        "image": None,  # filled in by image extraction pass
        "has_image": False,
    }


# ──────────────────────────────────────────────────────────────────────────────
# IMAGE ASSOCIATION
# ──────────────────────────────────────────────────────────────────────────────
def associate_images(questions: list, pdf_path: Path):
    """
    For each question, check if its page (or the next page) has embedded
    images and attach the largest one as Base64.
    """
    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count

    # Build page → images map
    log("  Scanning pages for embedded images…")
    page_images: dict[int, list] = {}
    for pn in range(total_pages):
        imgs = get_embedded_images_on_page(doc, pn)
        if imgs:
            page_images[pn] = imgs

    log(f"  Pages with images: {len(page_images)}")

    for q in questions:
        page_0 = q["page"] - 1  # back to 0-indexed
        # Check current page and next page (explanation may be on next page)
        for check_page in [page_0, page_0 + 1]:
            if check_page in page_images:
                imgs = page_images[check_page]
                if imgs:
                    # Pick largest image by area
                    best = max(imgs, key=lambda x: (x[2]-x[0]) * (x[3]-x[1]))
                    q["image"] = best[4]  # base64 string
                    q["has_image"] = True
                    break

    doc.close()
    return questions


# ──────────────────────────────────────────────────────────────────────────────
# REPORT
# ──────────────────────────────────────────────────────────────────────────────
def write_report(questions: list, report_path: Path):
    total = len(questions)
    with_image = sum(1 for q in questions if q["has_image"])
    with_answer = sum(1 for q in questions if q["correct_answer"])
    with_hint = sum(1 for q in questions if q["hint"])
    with_explanation = sum(1 for q in questions if q["explanation"])
    abcd_q = sum(1 for q in questions if q["option_type"] == "ABCD")
    pqrs_q = sum(1 for q in questions if q["option_type"] == "PQRS")
    chapters = {}
    for q in questions:
        ch = q["chapter"]
        chapters[ch] = chapters.get(ch, 0) + 1

    lines = [
        "=" * 60,
        " MATHS OLYMPIAD — EXTRACTION REPORT",
        "=" * 60,
        f"  Total questions extracted : {total}",
        f"  Questions with images     : {with_image}",
        f"  Questions with answer     : {with_answer}",
        f"  Questions with hint       : {with_hint}",
        f"  Questions with explanation: {with_explanation}",
        f"  A/B/C/D option questions  : {abcd_q}",
        f"  P/Q/R/S option questions  : {pqrs_q}",
        "",
        "  Chapter breakdown:",
    ]
    for ch, count in sorted(chapters.items(), key=lambda x: -x[1]):
        lines.append(f"    {ch}: {count} questions")

    lines += [
        "",
        "  Missing data:",
    ]
    missing_ans = [q["id"] for q in questions if not q["correct_answer"]]
    if missing_ans:
        lines.append(f"    No correct_answer: Q{missing_ans[:20]} {'...' if len(missing_ans)>20 else ''}")
    missing_opts = [q["id"] for q in questions if len(q["options"]) < 2]
    if missing_opts:
        lines.append(f"    < 2 options found: Q{missing_opts[:20]} {'...' if len(missing_opts)>20 else ''}")

    report = "\n".join(lines)
    report_path.write_text(report, encoding="utf-8")
    log("\n" + report)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    if not PDF_PATH.exists():
        sys.exit(f"ERROR: PDF not found at {PDF_PATH}")

    log(f"Opening: {PDF_PATH}")

    # ── Scan structure of first few pages ────────────────────────────────────
    scan_structure(PDF_PATH)

    # ── Extract full text ─────────────────────────────────────────────────────
    log("\nExtracting full text from PDF…")
    pages_text = extract_full_text(PDF_PATH)

    # ── Parse questions ───────────────────────────────────────────────────────
    log("\nParsing question blocks…")
    questions = parse_questions_from_pages(pages_text)
    log(f"Parsed {len(questions)} questions")

    # ── Associate images ──────────────────────────────────────────────────────
    log("\nAssociating images with questions…")
    questions = associate_images(questions, PDF_PATH)

    # ── Write JSON ────────────────────────────────────────────────────────────
    log(f"\nWriting {OUTPUT_JSON}…")
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    log(f"  Saved {OUTPUT_JSON.stat().st_size // 1024} KB")

    # ── Write report ──────────────────────────────────────────────────────────
    write_report(questions, REPORT_PATH)
    log(f"\nDone! Check {OUTPUT_JSON} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
