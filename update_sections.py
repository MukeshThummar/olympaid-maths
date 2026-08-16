import json
import os

def carry_forward_sections():
    print("Loading questions.json...")
    with open('questions.json', 'r', encoding='utf-8') as f:
        questions = json.load(f)

    # 1. Carry forward the section property
    current_chapter = None
    current_section = None
    
    modified_count = 0

    for q in questions:
        ch = q.get('chapter')
        if ch != current_chapter:
            current_chapter = ch
            current_section = None # Reset section on new chapter
            
        sec = q.get('section')
        if sec:
            current_section = sec
        elif current_section:
            q['section'] = current_section
            modified_count += 1
            
    print(f"Carried forward section for {modified_count} questions.")

    # Save back to questions.json
    with open('questions.json', 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    # 2. Regroup by chapter and recreate the chunk files
    chapters = {}
    for q in questions:
        ch = q.get('chapter', 'Unknown Chapter')
        if ch not in chapters:
            chapters[ch] = []
        chapters[ch].append(q)

    print("Regenerating chapter JS files...")
    chapter_index = []
    os.makedirs('data', exist_ok=True)
    
    for i, (ch_name, qs) in enumerate(chapters.items()):
        filename = f"chapter_{i+1}.js"
        chunk_path = os.path.join('data', filename)
        with open(chunk_path, 'w', encoding='utf-8') as f:
            js_content = f"window.olympiadData = window.olympiadData || {{}};\nwindow.olympiadData['{filename}'] = " + json.dumps(qs, ensure_ascii=False) + ";"
            f.write(js_content)
            
        chapter_index.append({
            'id': i + 1,
            'title': ch_name,
            'file': filename,
            'questionCount': len(qs)
        })

    with open('data/index.js', 'w', encoding='utf-8') as f:
        f.write("const chapterIndex = " + json.dumps(chapter_index, ensure_ascii=False, indent=2) + ";")
        
    print("All done! Sections are now correctly carried forward.")

if __name__ == '__main__':
    carry_forward_sections()
