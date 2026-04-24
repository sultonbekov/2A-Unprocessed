"""
KOSMIK Arxivlash - Sozlamalar (konstantalar)
Bu fayl barcha umumiy parametrlarni saqlaydi.
"""

# Fayllarni o'qish uchun bufer hajmi (8 MB).
# Katta bufer = tezroq o'qish katta fayllarda (5 TB+).
IO_BUFFER_SIZE = 8 * 1024 * 1024

# Viloyat strukturasi: Viloyat/Unprocessed/2A
UNPROCESSED_DIR = "Unprocessed"
TARGET_DIR = "2A"

# Yaratilgan arxivning nomi
ARCHIVE_NAME = "2A.7z"

# Progress qancha baytdan keyin yangilansin (128 MB)
PROGRESS_UPDATE_BYTES = 128 * 1024 * 1024

# Server porti
SERVER_PORT = 5000
