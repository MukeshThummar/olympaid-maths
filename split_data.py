import json
import os
import re

with open('questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

# Group by chapter
chapters = {}
for q in questions:
    ch = q.get('chapter', 'Unknown Chapter')
    if ch not in chapters:
        chapters[ch] = []
    chapters[ch].append(q)

os.makedirs('data', exist_ok=True)

chapter_index = []
for i, (ch_name, qs) in enumerate(chapters.items()):
    # Sanitize chapter name for filename
    filename = f"chapter_{i+1}.js"
    
    # Save the chunk
    chunk_path = os.path.join('data', filename)
    with open(chunk_path, 'w', encoding='utf-8') as f:
        # We assign it to a global variable corresponding to the chapter
        js_content = f"window.olympiadData = window.olympiadData || {{}};\nwindow.olympiadData['{filename}'] = " + json.dumps(qs, ensure_ascii=False) + ";"
        f.write(js_content)
        
    chapter_index.append({
        'id': i + 1,
        'title': ch_name,
        'file': filename,
        'questionCount': len(qs)
    })

# Write the index file
with open('data/index.js', 'w', encoding='utf-8') as f:
    f.write("const chapterIndex = " + json.dumps(chapter_index, ensure_ascii=False, indent=2) + ";")

print(f"Successfully split into {len(chapters)} chunks in the 'data' folder.")
