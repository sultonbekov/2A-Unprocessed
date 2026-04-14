"""
Viloyat Archiver - Professional ZIP Archive Tool
Backend API for archiving 2A folders from Viloyat/Unprocessed structure
"""

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import zipfile
import shutil
import tempfile
import webbrowser
import threading
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the frontend directory path
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / 'frontend'

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path='')
CORS(app)


class ViloyatArchiver:
    """Professional archiver for Viloyat folder structures"""
    
    def __init__(self):
        self.supported_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.png', '.txt']
    
    def validate_input_path(self, input_path: str) -> dict:
        """Validate the input folder structure - finds all Viloyat folders"""
        path = Path(input_path)
        
        if not path.exists():
            return {"valid": False, "error": "Путь не существует"}
        
        if not path.is_dir():
            return {"valid": False, "error": "Путь не является папкой"}
        
        # Find all Viloyat folders with Unprocessed/2A structure
        viloyats = []
        total_files = 0
        
        for item in path.iterdir():
            if item.is_dir():
                unprocessed_path = item / "Unprocessed"
                folder_2a = unprocessed_path / "2A"
                
                if unprocessed_path.exists() and folder_2a.exists():
                    file_count = self._count_files(folder_2a)
                    viloyats.append({
                        "name": item.name,
                        "path": str(item),
                        "folder_2a_path": str(folder_2a),
                        "file_count": file_count
                    })
                    total_files += file_count
        
        if not viloyats:
            return {"valid": False, "error": "Вилоятлар топилмади (Unprocessed/2A структураси йўқ)"}
        
        return {
            "valid": True,
            "viloyat_count": len(viloyats),
            "viloyats": viloyats,
            "total_files": total_files
        }
    
    def _count_files(self, folder_path: Path) -> int:
        """Count all files in a folder recursively"""
        count = 0
        for item in folder_path.rglob("*"):
            if item.is_file():
                count += 1
        return count
    
    def create_archive(self, input_path: str, output_path: str) -> dict:
        """Create ZIP archives for all Viloyat folders"""
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)
            
            # Validate input
            validation = self.validate_input_path(str(input_path))
            if not validation["valid"]:
                return {"success": False, "error": validation["error"]}
            
            viloyats = validation["viloyats"]
            results = []
            total_files_archived = 0
            total_original_size = 0
            total_archive_size = 0
            
            for viloyat in viloyats:
                viloyat_name = viloyat["name"]
                folder_2a = Path(viloyat["folder_2a_path"])
                
                # Create output directory structure: output/ViloyatName/
                viloyat_output = output_path / viloyat_name
                viloyat_output.mkdir(parents=True, exist_ok=True)
                
                # Create ZIP file: output/ViloyatName/2A.zip
                zip_filename = viloyat_output / "2A.zip"
                
                # Create the archive
                files_archived = 0
                original_size = 0
                
                with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in folder_2a.rglob("*"):
                        if file_path.is_file():
                            arcname = file_path.relative_to(folder_2a)
                            zipf.write(file_path, arcname)
                            files_archived += 1
                            original_size += file_path.stat().st_size
                
                archive_size = zip_filename.stat().st_size
                
                results.append({
                    "viloyat_name": viloyat_name,
                    "archive_path": str(zip_filename),
                    "files_archived": files_archived,
                    "original_size": original_size,
                    "archive_size": archive_size
                })
                
                total_files_archived += files_archived
                total_original_size += original_size
                total_archive_size += archive_size
                
                logger.info(f"Archive created: {zip_filename}")
            
            compression_ratio = (1 - total_archive_size / total_original_size) * 100 if total_original_size > 0 else 0
            
            return {
                "success": True,
                "viloyat_count": len(results),
                "viloyats": results,
                "files_archived": total_files_archived,
                "original_size": self._format_size(total_original_size),
                "archive_size": self._format_size(total_archive_size),
                "compression_ratio": f"{compression_ratio:.1f}%",
                "output_path": str(output_path),
                "created_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Archive creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"


# Initialize archiver
archiver = ViloyatArchiver()


@app.route('/')
def serve_frontend():
    """Serve the frontend application"""
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory(FRONTEND_DIR, path)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "Viloyat Archiver"})


@app.route('/api/validate', methods=['POST'])
def validate_path():
    """Validate input folder structure"""
    data = request.get_json()
    input_path = data.get('input_path', '')
    
    if not input_path:
        return jsonify({"valid": False, "error": "Укажите входной путь"}), 400
    
    result = archiver.validate_input_path(input_path)
    return jsonify(result)


@app.route('/api/archive', methods=['POST'])
def create_archive():
    """Create ZIP archive"""
    data = request.get_json()
    input_path = data.get('input_path', '')
    output_path = data.get('output_path', '')
    
    if not input_path or not output_path:
        return jsonify({"success": False, "error": "Укажите входной и выходной пути"}), 400
    
    result = archiver.create_archive(input_path, output_path)
    
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/browse', methods=['POST'])
def browse_directory():
    """Browse directory contents"""
    data = request.get_json()
    path = data.get('path', '')
    
    if not path:
        # Return drives on Windows
        import string
        drives = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append({"name": drive, "type": "drive"})
        return jsonify({"items": drives, "current_path": ""})
    
    try:
        path = Path(path)
        if not path.exists():
            return jsonify({"error": "Путь не существует"}), 400
        
        items = []
        for item in sorted(path.iterdir()):
            items.append({
                "name": item.name,
                "path": str(item),
                "type": "folder" if item.is_dir() else "file"
            })
        
        return jsonify({
            "items": items,
            "current_path": str(path),
            "parent_path": str(path.parent) if path.parent != path else None
        })
    except PermissionError:
        return jsonify({"error": "Доступ запрещён"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def open_browser():
    """Open browser after server starts"""
    webbrowser.open('http://localhost:5000')


if __name__ == '__main__':
    print("\n" + "="*50)
    print("   KOSMIK - Arxivlash Tizimi")
    print("="*50)
    print(f"\n   Frontend: {FRONTEND_DIR}")
    print("   Server:   http://localhost:5000")
    print("\n   Opening browser...")
    print("="*50 + "\n")
    
    # Open browser after a short delay
    threading.Timer(1.5, open_browser).start()
    
    app.run(debug=False, port=5000, threaded=True)
