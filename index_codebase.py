import os
import requests

API_URL = "http://localhost:5004/index-code"

def index_directory(directory, extensions=['.py', '.js', '.html', '.css']):
    for root, dirs, files in os.walk(directory):
        # Skip venv and node_modules
        dirs[:] = [d for d in dirs if d not in ['venv', 'venv-windwos', 'node_modules', '__pycache__', '.git']]
        
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    ext = os.path.splitext(file)[1][1:]
                    language = {'py': 'python', 'js': 'javascript', 'html': 'html', 'css': 'css'}.get(ext, ext)
                    
                    response = requests.post(API_URL, json={
                        'file_path': filepath,
                        'content': content,
                        'language': language
                    })
                    
                    if response.ok:
                        print(f"✓ Indexed: {filepath}")
                    else:
                        print(f"✗ Failed: {filepath}")
                except Exception as e:
                    print(f"✗ Error reading {filepath}: {e}")

if __name__ == '__main__':
    project_dir = os.path.dirname(os.path.dirname(__file__))
    print(f"Indexing codebase from: {project_dir}")
    index_directory(project_dir)
    print("\nIndexing complete!")
