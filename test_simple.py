"""
Prostoy test - proverka raboti archive.py
"""

import tempfile
import random
import subprocess
import sys
from pathlib import Path


def create_test_structure(root: Path):
    """Mock struktura yaratish"""
    viloyats = ["Andijon", "Buxoro"]
    for vname in viloyats:
        target = root / vname / "Unprocessed" / "2A"
        target.mkdir(parents=True, exist_ok=True)
        
        for i in range(5):
            file_path = target / f"file_{i}.txt"
            file_path.write_text(f"Test data {i} from {vname}\n" * 100)
    
    return viloyats


def main():
    print("=" * 70)
    print("  Test: archive.py")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        input_dir = tmp_root / "input"
        output_dir = tmp_root / "output"
        input_dir.mkdir()
        
        print("\n1. Mock ma'lumot yaratish...")
        viloyats = create_test_structure(input_dir)
        print(f"   Yaratildi: {len(viloyats)} viloyat")
        
        print("\n2. Arxivlash...")
        result = subprocess.run(
            [sys.executable, "archive.py", str(input_dir), str(output_dir)],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print(f"\n✗ XATO: {result.stderr}")
            return False
        
        print(result.stdout)
        
        print("\n3. Natijani tekshirish...")
        for vname in viloyats:
            archive_path = output_dir / vname / "2A.7z"
            if not archive_path.exists():
                print(f"   ✗ Arxiv topilmadi: {archive_path}")
                return False
            size = archive_path.stat().st_size
            print(f"   ✓ {vname}/2A.7z ({size} bytes)")
        
        print("\n" + "=" * 70)
        print("  ✓ HAMMA TESTLAR MUVAFFAQIYATLI!")
        print("=" * 70)
        return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
