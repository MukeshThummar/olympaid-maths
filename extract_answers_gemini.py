#!/usr/bin/env python3
import os
import sys
import json
import io
import time
from pathlib import Path

import fitz
from PIL import Image
from google import genai
from google.genai import types
import re

PDF_PATH = Path("docs/Maths Olympiad workbook.pdf")
QUESTIONS_JSON = Path("questions.json")
START_PAGE = 56 # 0-indexed page where Hints & Explanations start

def get_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        key_file = Path("gemini_api_key.txt")
        if key_file.exists():
            api_key = key_file.read_text().strip()
    return api_key

def render_page(doc: fitz.Document, page_num: int, dpi: int = 200) -> bytes:
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()

PROMPT = """You are an expert at extracting answer keys and explanations from Olympiad workbooks.
Analyze this page from the "Hints & Explanations" section.
Extract the correct answers, hints, and explanations for each question.
The format is usually "Q_Number. (Answer) : Explanation text" or just "Q_Number. (Answer)"

Return a JSON object with this exact structure (no markdown fences, just JSON):
{
  "chapter": "Current Chapter Name if a new chapter starts on this page, else null",
  "answers": [
    {
      "id": 1,
      "correct_answer": "B",
      "explanation": "100 thousands = 1,00,000 = 1 lakh",
      "hint": null
    },
    ...
  ]
}
Note: 
- "id" is the integer question number.
- "correct_answer" is the letter A, B, C, or D.
- "explanation" is the full text of the explanation if present, else null.
- If it says "Hint:" put that text in "hint".
- Be precise and capture all questions on the page.
"""

def extract_answers(client, jpeg_bytes):
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=[
                    types.Part.from_text(text=PROMPT),
                    types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                ],
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=8192),
            )
            text = response.text.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
            text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
            return json.loads(text.strip())
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)
    return None

def main():
    with open(QUESTIONS_JSON, "r", encoding="utf-8") as f:
        questions = json.load(f)

    # Group existing questions by chapter for easier matching
    chapter_names = list(dict.fromkeys(q["chapter"] for q in questions if q.get("chapter")))
    current_chapter_idx = 0
    
    doc = fitz.open(PDF_PATH)
    client = genai.Client(api_key=get_api_key())
    
    extracted_data = []

    for page_num in range(START_PAGE, doc.page_count):
        print(f"Processing page {page_num+1}/{doc.page_count} for answers...")
        jpeg_bytes = render_page(doc, page_num)
        result = extract_answers(client, jpeg_bytes)
        if result and "answers" in result and result["answers"]:
            if result.get("chapter"):
                # Use the next available chapter from the questions list if it roughly matches, or just increment
                # To be safe, we rely on the sequential order of chapters.
                # Assuming the answer key chapters are in the same order.
                print(f"Detected chapter in answers: {result['chapter']}")
            extracted_data.append(result)
        time.sleep(2)
    doc.close()

    # Now merge back into questions
    # We will iterate through extracted answers, assigning them to chapters in order.
    current_q_chapter = chapter_names[0] if chapter_names else None
    chapter_idx = 0
    
    for page_data in extracted_data:
        if page_data.get("chapter") and chapter_idx < len(chapter_names):
            # Check if this chapter string roughly indicates the next chapter
            # We'll just advance chapter_idx when the id drops back to 1
            pass
            
        for ans in page_data["answers"]:
            q_id = ans["id"]
            # If q_id is 1 and it's not the first item, we might have advanced a chapter.
            # We will manually track chapter advancement based on q_id resetting to 1.
            
    # Actually, a better way to merge is to advance chapter index whenever the answer id drops significantly (e.g. from 30 back to 1)
    
    merged_count = 0
    q_idx = 0
    
    # Flatten answers with a chapter marker
    flat_answers = []
    current_ch = 0
    last_id = 0
    for page_data in extracted_data:
        for ans in page_data["answers"]:
            if ans["id"] <= 5 and last_id > 15:
                current_ch += 1
            flat_answers.append({
                "chapter_idx": current_ch,
                "id": ans["id"],
                "correct_answer": ans["correct_answer"],
                "explanation": ans["explanation"],
                "hint": ans.get("hint")
            })
            last_id = ans["id"]

    for ans in flat_answers:
        if ans["chapter_idx"] < len(chapter_names):
            ch_name = chapter_names[ans["chapter_idx"]]
            # Find the question with this chapter and id
            for q in questions:
                if q["chapter"] == ch_name and q["id"] == ans["id"]:
                    q["correct_answer"] = ans["correct_answer"]
                    if ans["explanation"]:
                        q["explanation"] = ans["explanation"]
                    if ans.get("hint"):
                        q["hint"] = ans["hint"]
                    merged_count += 1
                    break

    with open(QUESTIONS_JSON, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        
    print(f"Merged {merged_count} answers into questions.json!")

if __name__ == "__main__":
    main()
