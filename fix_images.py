import json
import os
import base64

def fix_images_and_chunks():
    print("Loading questions.json...")
    with open('questions.json', 'r', encoding='utf-8') as f:
        questions = json.load(f)

    img_count = 0
    os.makedirs('data/images', exist_ok=True)

    for q in questions:
        if q.get('has_graphic') and q.get('page_image'):
            b64_data = q['page_image']
            
            # If it's still base64, convert to local file reference
            if b64_data.startswith('data:image'):
                header, encoded = b64_data.split(',', 1)
                ext = 'jpg'
                if 'png' in header:
                    ext = 'png'
                
                global_id = q.get('global_id', q.get('id', img_count))
                image_filename = f"img_q{global_id}.{ext}"
                image_path = os.path.join('data', 'images', image_filename)
                
                # We already extracted the files previously, but we can write them again to be safe
                with open(image_path, 'wb') as img_f:
                    img_f.write(base64.b64decode(encoded))
                
                q['page_image'] = f"data/images/{image_filename}"
                img_count += 1

    print(f"Updated {img_count} image references.")

    # IMPORTANT: Save back to questions.json so it persists!
    with open('questions.json', 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    # Group by chapter and recreate chunks
    chapters = {}
    for q in questions:
        ch = q.get('chapter', 'Unknown Chapter')
        if ch not in chapters:
            chapters[ch] = []
        chapters[ch].append(q)

    print("Regenerating chapter JS files...")
    chapter_index = []
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
        
    print("Fixed! Image paths are updated and JS chunks regenerated.")

if __name__ == '__main__':
    fix_images_and_chunks()
