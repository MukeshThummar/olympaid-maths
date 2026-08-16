#!/usr/bin/env python3
"""
Maths Olympiad PDF Extractor — Gemini Vision Powered (v2)
==========================================================
Uses Google Gemini Vision API (google-genai SDK) to extract MCQ questions
from each page of the scanned PDF workbook. Handles:
  - Text questions
  - Graphical/image-based questions (charts, diagrams, pictographs, clocks)
  - A/B/C/D and P/Q/R/S option formats
  - Chapters, hints, explanations
  - Question images embedded as Base64 in output JSON

Requirements:
  pip install pymupdf pillow google-genai

Usage:
  python extract_with_gemini.py
  (API key read from gemini_api_key.txt or GEMINI_API_KEY env var)
"""

import os
import sys
import json
import base64
import io
import re
import time
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        sys.exit("ERROR: pymupdf not installed. Run: pip install pymupdf")

try:
    from PIL import Image
except ImportError:
    sys.exit("ERROR: Pillow not installed. Run: pip install pillow")

try:
    from google import genai
    from google.genai import types
except ImportError:
    sys.exit("ERROR: google-genai not installed. Run: pip install google-genai")

# ─────────────────────────────────────────────────────────────────────────────
PDF_PATH        = Path("docs/Maths Olympiad workbook.pdf")
OUTPUT_JSON     = Path("questions.json")
PROGRESS_JSON   = Path("questions_progress.json")   # Checkpoint per page
REPORT_PATH     = Path("extraction_report.txt")
PAGE_RENDER_DPI = 200
RETRY_ATTEMPTS  = 3
RETRY_DELAY_SEC = 5
MODEL_NAME      = "gemini-3.1-flash-lite"           # Confirmed working model
# ─────────────────────────────────────────────────────────────────────────────


def log(msg: str):
    print(msg, flush=True)


# ──────────────────────────────────────────────────────────────────────────────
# GEMINI SETUP
# ──────────────────────────────────────────────────────────────────────────────
def get_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        key_file = Path("gemini_api_key.txt")
        if key_file.exists():
            api_key = key_file.read_text().strip()
    if not api_key:
        sys.exit(
            "ERROR: No Gemini API key found.\n"
            "Set the GEMINI_API_KEY env var or create gemini_api_key.txt"
        )
    return api_key


def list_available_models(client: genai.Client):
    """List available Gemini models to pick the right one."""
    try:
        models = client.models.list()
        flash_models = [m.name for m in models if "flash" in m.name.lower()]
        log(f"  Available flash models: {flash_models[:6]}")
        return flash_models
    except Exception as e:
        log(f"  Could not list models: {e}")
        return []


def setup_gemini() -> tuple[genai.Client, str]:
    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    # Find the best available model
    log("Checking available Gemini models…")
    available = list_available_models(client)

    preferred = [
        "models/gemini-3.1-flash-lite",
        "models/gemini-flash-lite-latest",
        "models/gemini-3.5-flash",
        "models/gemini-flash-latest",
        "models/gemini-3.1-flash-image",
    ]
    model_name = MODEL_NAME
    for pref in preferred:
        if pref in available:
            model_name = pref
            break

    log(f"Using model: {model_name}")
    return client, model_name


# ──────────────────────────────────────────────────────────────────────────────
# PDF → PAGE IMAGES
# ──────────────────────────────────────────────────────────────────────────────
def render_page(doc: fitz.Document, page_num: int, dpi: int = PAGE_RENDER_DPI) -> bytes:
    """Render a PDF page and return JPEG bytes."""
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    # Convert to JPEG for smaller payload
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def jpeg_bytes_to_base64(jpeg_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()


# ──────────────────────────────────────────────────────────────────────────────
# GEMINI PROMPT
# ──────────────────────────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """You are an expert at extracting MCQ questions from Maths Olympiad (IMO) workbook pages for Class 4 students.

Analyze this page image carefully and extract ALL questions present on this page.

For EACH question return a JSON object with these exact fields:
- "id": question number as integer (e.g., 1, 2, 3...) — local number as printed on the page
- "section": section name if visible (e.g., "Mathematical Reasoning", "Achievers Section (HOTS)") or null
- "question": the COMPLETE question text — preserve ALL text exactly, including:
    * Sub-statements labeled P, Q, R, S
    * Fill-in-the-blank underscores
    * Numbers from diagrams/tables that are part of the question
    * Column-I and Column-II items for matching questions
- "has_graphic": true if the question contains ANY visual element (diagram, image, chart, graph, table, pictograph, clock, abacus, number cards, shapes, figures); false otherwise
- "graphic_description": brief description of the graphic if has_graphic is true, else null
  Example: "bar graph showing donations Jan-May", "clock showing 7:45", "number cards 9 4 3 8 2", "abacus with beads on columns"
- "option_type": 
    * "ABCD" — standard questions where answer choices are labeled (A), (B), (C), (D)
    * "PQRS" — matching/column questions where sub-items P,Q,R,S are matched, but final answer choices are still (A)/(B)/(C)/(D)
- "options": object with the answer choice letters as keys and their text as values.
    * Always use keys "A", "B", "C", "D" for the four answer choices
    * For PQRS questions: the four answer choices (A)/(B)/(C)/(D) show different P-Q-R-S combinations — include them exactly
- "correct_answer": ONLY if an answer key is shown on THIS page — the letter (A/B/C/D); else null
- "hint": hint text if visible on this page, else null
- "explanation": explanation or solution text if visible on this page, else null

IMPORTANT RULES:
1. Extract EVERY question on the page without skipping any
2. If the page shows a CHAPTER header (e.g., "CHAPTER 4 Length, Weight, Capacity, Time and Money"), include it
3. Question numbers restart at 1 for each new chapter
4. For graphical questions, transcribe all visible text/numbers FROM the graphic into the question field so the question is self-contained
5. Do NOT invent or guess answers — only fill correct_answer if explicitly shown as an answer key
6. Preserve ALL mathematical symbols: ₹, ×, ÷, +, –, fractions (write as e.g. "2 3/4"), >, <, =
7. For "Compare and fill the box" questions, include the box □ as [] in the question text
8. If this is a chapter cover page or a blank page, return empty questions array

Return ONLY valid JSON — no markdown fences, no explanation text:
{
  "chapter": "Chapter X: Title" or null,
  "page_type": "chapter_cover" | "questions" | "answer_key" | "blank",
  "questions": [
    {
      "id": 1,
      "section": "Mathematical Reasoning",
      "question": "Full question text here...",
      "has_graphic": false,
      "graphic_description": null,
      "option_type": "ABCD",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct_answer": null,
      "hint": null,
      "explanation": null
    }
  ]
}"""


# ──────────────────────────────────────────────────────────────────────────────
# GEMINI API CALL WITH RETRY
# ──────────────────────────────────────────────────────────────────────────────
def extract_page_questions(
    client: genai.Client,
    model_name: str,
    jpeg_bytes: bytes,
    page_num: int,
) -> dict | None:
    """Call Gemini Vision API to extract questions from a JPEG page image."""

    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_text(text=EXTRACTION_PROMPT),
                    types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=8192,
                ),
            )
            text = response.text.strip()

            # Strip markdown code fences if present
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
            text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
            text = text.strip()

            data = json.loads(text)
            return data

        except json.JSONDecodeError as e:
            log(f"  [Page {page_num+1}] JSON parse error (attempt {attempt+1}): {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SEC)
        except Exception as e:
            err_str = str(e)
            log(f"  [Page {page_num+1}] API error (attempt {attempt+1}): {err_str[:250]}")
            if "quota" in err_str.lower() or "429" in err_str:
                log("  Rate limit — waiting 65s…")
                time.sleep(65)
            elif "503" in err_str or "overloaded" in err_str.lower():
                log("  Server busy — waiting 30s…")
                time.sleep(30)
            elif attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SEC)

    log(f"  [Page {page_num+1}] Failed after {RETRY_ATTEMPTS} attempts — skipping")
    return None


# ──────────────────────────────────────────────────────────────────────────────
# CHECKPOINT SAVE / LOAD
# ──────────────────────────────────────────────────────────────────────────────
def save_checkpoint(questions: list, processed_pages: set, current_chapter: str):
    checkpoint = {
        "questions": questions,
        "processed_pages": list(processed_pages),
        "current_chapter": current_chapter,
    }
    with open(PROGRESS_JSON, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False)


def load_checkpoint() -> tuple[list, set, str]:
    if PROGRESS_JSON.exists():
        log(f"Loading checkpoint from {PROGRESS_JSON}…")
        with open(PROGRESS_JSON, "r", encoding="utf-8") as f:
            cp = json.load(f)
        questions = cp.get("questions", [])
        processed = set(cp.get("processed_pages", []))
        chapter = cp.get("current_chapter", "Unknown Chapter")
        log(f"  Resuming: {len(processed)} pages done, {len(questions)} questions so far")
        return questions, processed, chapter
    return [], set(), "Unknown Chapter"


# ──────────────────────────────────────────────────────────────────────────────
# FINAL JSON BUILDER
# ──────────────────────────────────────────────────────────────────────────────
def build_final_json(all_questions: list) -> list:
    cleaned = []
    for q in all_questions:
        cleaned.append({
            "global_id":           q.get("global_id"),
            "chapter":             q.get("chapter"),
            "pdf_page":            q.get("pdf_page"),
            "section":             q.get("section"),
            "id":                  q.get("id"),
            "question":            q.get("question", ""),
            "option_type":         q.get("option_type", "ABCD"),
            "options":             q.get("options", {}),
            "correct_answer":      q.get("correct_answer"),
            "hint":                q.get("hint"),
            "explanation":         q.get("explanation"),
            "has_graphic":         q.get("has_graphic", False),
            "graphic_description": q.get("graphic_description"),
            "page_image":          q.get("page_image"),  # Base64 JPEG of page (graphic Qs only)
        })
    return cleaned


# ──────────────────────────────────────────────────────────────────────────────
# REPORT WRITER
# ──────────────────────────────────────────────────────────────────────────────
def write_report(questions: list):
    total        = len(questions)
    with_graphic = sum(1 for q in questions if q.get("has_graphic"))
    with_answer  = sum(1 for q in questions if q.get("correct_answer"))
    with_hint    = sum(1 for q in questions if q.get("hint"))
    with_expl    = sum(1 for q in questions if q.get("explanation"))
    abcd_q       = sum(1 for q in questions if q.get("option_type") == "ABCD")
    pqrs_q       = sum(1 for q in questions if q.get("option_type") == "PQRS")

    chapters: dict[str, int] = {}
    for q in questions:
        ch = q.get("chapter", "Unknown")
        chapters[ch] = chapters.get(ch, 0) + 1

    lines = [
        "=" * 64,
        "  MATHS OLYMPIAD (IMO) — EXTRACTION REPORT",
        "=" * 64,
        f"  Total questions extracted     : {total}",
        f"  Questions with graphics       : {with_graphic}",
        f"  Questions with correct answer : {with_answer}",
        f"  Questions with hint           : {with_hint}",
        f"  Questions with explanation    : {with_expl}",
        f"  A/B/C/D type questions        : {abcd_q}",
        f"  P/Q/R/S type questions        : {pqrs_q}",
        "",
        "  Chapter breakdown:",
    ]
    for ch, count in sorted(chapters.items()):
        lines.append(f"    {ch:<48} : {count} questions")

    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log("\n" + report)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    if not PDF_PATH.exists():
        sys.exit(f"ERROR: PDF not found at {PDF_PATH}")

    # Setup Gemini client
    client, model_name = setup_gemini()

    # Open PDF
    doc = fitz.open(str(PDF_PATH))
    total_pages = doc.page_count
    log(f"\nPDF: {PDF_PATH}  |  {total_pages} pages")

    # Load checkpoint
    all_questions, processed_pages, current_chapter = load_checkpoint()
    global_q_counter = max((q.get("global_id", 0) for q in all_questions), default=0)

    # Process each page
    for page_num in range(total_pages):
        if page_num in processed_pages:
            log(f"  [Page {page_num+1}/{total_pages}] Already done — skipping")
            continue

        log(f"\n[Page {page_num+1}/{total_pages}] Rendering…")
        jpeg_bytes = render_page(doc, page_num)

        log(f"[Page {page_num+1}/{total_pages}] Calling Gemini ({model_name})…")
        result = extract_page_questions(client, model_name, jpeg_bytes, page_num)

        if result is None:
            processed_pages.add(page_num)
            save_checkpoint(all_questions, processed_pages, current_chapter)
            continue

        page_type = result.get("page_type", "questions")
        log(f"  page_type: {page_type}")

        if page_type in ("blank", "answer_key"):
            log(f"  Skipping page type: {page_type}")
            processed_pages.add(page_num)
            save_checkpoint(all_questions, processed_pages, current_chapter)
            continue

        # Update chapter if a new one starts on this page
        if result.get("chapter"):
            current_chapter = result["chapter"]
            log(f"  ★ New chapter: {current_chapter}")

        questions_on_page = result.get("questions", [])
        log(f"  → {len(questions_on_page)} questions extracted")

        page_b64 = jpeg_bytes_to_base64(jpeg_bytes)

        for q in questions_on_page:
            global_q_counter += 1
            q["global_id"] = global_q_counter
            q["chapter"]   = current_chapter
            q["pdf_page"]  = page_num + 1
            # Attach page image only for graphical questions (saves file size)
            q["page_image"] = page_b64 if q.get("has_graphic") else None
            if q.get("has_graphic"):
                log(f"    [Q{q.get('id')}] graphic: {q.get('graphic_description', '')[:60]}")

        all_questions.extend(questions_on_page)
        processed_pages.add(page_num)
        save_checkpoint(all_questions, processed_pages, current_chapter)

        # Polite delay between API calls
        time.sleep(2)

    doc.close()

    # Write final clean JSON
    log(f"\nWriting {OUTPUT_JSON}…")
    final = build_final_json(all_questions)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    size_kb = OUTPUT_JSON.stat().st_size // 1024
    log(f"  ✅ Saved {OUTPUT_JSON} — {size_kb} KB — {len(final)} questions")

    write_report(final)
    log(f"\n✅ All done! Review:\n  {OUTPUT_JSON}\n  {REPORT_PATH}")


if __name__ == "__main__":
    main()
