"""Milestone 1 - turn the raw Jamalon dataset into a clean, balanced 200-book catalog.

    python -m bookrec.prepare_data

writes data/catalog.csv: the ONLY books the assistant is allowed to recommend.
Explored step by step in notebooks/01_data_exploration.ipynb.
"""
import hashlib
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd

KAGGLE_DATASET = "dareenalharthi/jamalon-arabic-books-dataset"
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"              # git-ignored download cache
CATALOG_PATH = ROOT / "data" / "catalog.csv"

# A product decision, not a statistical one: the 10 "shelves" our store carries.
CATEGORIES = [
    "الأدب والخيال",       # literature & fiction
    "الفلسفة",             # philosophy
    "الكتب الإسلامية",     # Islamic books
    "الاقتصاد والأعمال",   # economics & business
    "الكتب السياسية",      # politics
    "العلوم والطبيعة",     # science & nature
    "الأسرة والطفل",       # family & children
    "السير والمذكرات",     # biographies & memoirs
    "الفنون",              # arts
    "التاريخ والجغرافيا",  # history & geography
]
PER_CATEGORY = 20      # 10 x 20 = 200 books, every shelf equally represented
MIN_DESC_CHARS = 100   # the search engine needs enough text to match against
SEED = 42              # same seed -> the same 200 books on every machine

# Scraping leftovers (found in Milestone 2): text-direction marks saved as the literal
# text "u200e", or kept as invisible characters.
SCRAPE_ARTIFACTS = re.compile(r"u200[ef]|u202[a-e]|[\u200e\u200f\u202a-\u202e]")


def load_raw():
    """Download the public Kaggle dataset once (cached in data/raw/) and load it."""
    os.environ.setdefault("KAGGLEHUB_CACHE", str(RAW_DIR))
    import kagglehub  # imported after setting the cache folder

    folder = kagglehub.dataset_download(KAGGLE_DATASET)
    return pd.read_csv(next(Path(folder).rglob("*.csv")))


def clean_text(value):
    """Fix PDF 'presentation forms' (ﻣﺬﻛﺮات -> مذكرات), drop scraping leftovers, collapse whitespace."""
    if pd.isna(value):
        return ""
    text = SCRAPE_ARTIFACTS.sub(" ", unicodedata.normalize("NFKC", str(value)))
    return " ".join(text.split())


def build_catalog(raw):
    books = pd.DataFrame({
        "title": raw["Title"].map(clean_text),
        "author": raw["Author"].map(clean_text),
        "category": raw["Category"].map(clean_text),
        "subcategory": raw["Subcategory"].map(clean_text),
        "publisher": raw["Publisher"].map(clean_text),
        "year": raw["Publication year"].where(raw["Publication year"] > 0).astype("Int64"),  # 0 = unknown
        "pages": raw["Pages"].where(raw["Pages"] > 0).astype("Int64"),
        "description": raw["Description"].map(clean_text),
    })

    keep = (
        books["description"].str.len().ge(MIN_DESC_CHARS)  # drops "None" and one-liners
        & books["title"].ne("")
        & ~books["author"].isin(["", "لا يوجد"])           # "لا يوجد" = "none"
        & books["category"].isin(CATEGORIES)
    )
    books = books[keep].drop_duplicates(["title", "author"])

    shelves = []
    for category in CATEGORIES:
        shelf = books[books["category"] == category].sort_values(["title", "author"])
        pick = shelf.sample(n=PER_CATEGORY, random_state=SEED)
        shelves.append(pick.sort_values(["title", "author"]))
    catalog = pd.concat(shelves, ignore_index=True)
    catalog.insert(0, "book_id", [f"B{i:03d}" for i in range(1, len(catalog) + 1)])
    return catalog


def fingerprint(catalog):
    """Short hash of the CSV text: same fingerprint = the same 200 books, byte for byte."""
    text = catalog.to_csv(index=False, lineterminator="\n")
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


def main():
    raw = load_raw()
    catalog = build_catalog(raw)
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(CATALOG_PATH, index=False, lineterminator="\n")
    print(f"raw: {len(raw)} books -> catalog: {len(catalog)} books "
          f"({catalog['category'].nunique()} categories x {PER_CATEGORY})")
    print("fingerprint:", fingerprint(catalog))
    print("saved to", CATALOG_PATH.relative_to(ROOT))


if __name__ == "__main__":
    main()
