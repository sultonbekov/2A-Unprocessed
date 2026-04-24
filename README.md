# KOSMIK Arxivlash - Lokal versiya

Minimal 7z arxivlash dasturi (parallel, tezkor).

## Ishlatish

```bash
python archive.py "INPUT_PAPKA" "OUTPUT_PAPKA"
```

## Misol

```bash
python archive.py "D:\Data\Input" "D:\Data\Output"
```

## INPUT struktura

```
INPUT_PAPKA/
├── Andijon/
│   └── Unprocessed/
│       └── 2A/
│           ├── file1.pdf
│           ├── file2.jpg
│           └── ...
├── Buxoro/
│   └── Unprocessed/
│       └── 2A/
│           └── ...
└── ...
```

## OUTPUT natija

```
OUTPUT_PAPKA/
├── Andijon/
│   └── 2A.7z
├── Buxoro/
│   └── 2A.7z
└── ...
```

## O'rnatish

```bash
pip install py7zr
```

## Xususiyatlar

- **Faqat 7z** format (siqmasdan, eng tez)
- **Parallel** - har bir viloyat alohida thread
- **Xavfsiz** - manba fayllar o'zgartirilmaydi
- **Tezkor** - 8MB IO bufer, CPU parallel

## Test

```bash
python tests/test_integrity.py
```

20 ta test - manba ma'lumotlar o'zgarmasligini tekshiradi.
