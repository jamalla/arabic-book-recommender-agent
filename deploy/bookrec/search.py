"""Milestone 2 - a tiny search engine over the catalog: character-level TF-IDF.

No training and no API calls: indexing 200 books takes milliseconds and costs nothing.

    python -m bookrec.search "روايات عن الحب"
"""
import re
import sys
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "catalog.csv"

TASHKEEL = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")  # short vowels and marks
LETTER_VARIANTS = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",  # alef with hamza / madda -> bare alef
    "ة": "ه",                               # taa marbuta -> haa
    "ى": "ي",                               # alef maqsura -> yaa
    "ؤ": "و", "ئ": "ي",                     # hamza on waw / yaa
    "ـ": "",                                # tatweel (decorative stretching)
})


def normalize_arabic(text):
    """Map spelling variants to one form: «الإسلامية» and «الاسلاميه» both become «الاسلاميه»."""
    text = TASHKEEL.sub("", str(text)).translate(LETTER_VARIANTS)
    return " ".join(text.lower().split())


def book_documents(books):
    """The text a reader's request can match: title, author, category, subcategory, description."""
    columns = ["title", "author", "category", "subcategory", "description"]
    return books[columns].fillna("").astype(str).agg(" ".join, axis=1).map(normalize_arabic)


class BookSearch:
    """Index the catalog once, then answer many queries."""

    def __init__(self, catalog_path=CATALOG_PATH):
        self.books = pd.read_csv(catalog_path)
        # char_wb = character n-grams taken inside word boundaries, 2 to 4 letters long:
        # «رواية» and «روايات» share روا / واي / اي ..., so singular and plural still match.
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(book_documents(self.books))

    def search(self, query, k=5):
        """Return the k most similar books, best first, each with a 0-1 similarity score."""
        query_vector = self.vectorizer.transform([normalize_arabic(query)])
        scores = linear_kernel(query_vector, self.matrix).ravel()  # rows are L2-normalized -> cosine
        results = []
        for i in scores.argsort()[::-1][:k]:
            book = self.books.iloc[i]
            results.append({
                "book_id": book["book_id"],
                "title": book["title"],
                "author": book["author"],
                "category": book["category"],
                "year": None if pd.isna(book["year"]) else int(book["year"]),
                "description": book["description"][:300],
                "score": round(float(scores[i]), 3),
            })
        return results


if __name__ == "__main__":
    engine = BookSearch()
    query = " ".join(sys.argv[1:]) or "روايات عن الحب"
    for hit in engine.search(query):
        print(f"{hit['score']:.3f}  {hit['book_id']}  {hit['title']} - {hit['author']} ({hit['category']})")
