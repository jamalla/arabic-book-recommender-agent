"""Milestone 4 - the fixed test set: 12 reader questions, including TRAPS.

A trap asks for something that is NOT in the catalog. The right answer is honesty ("we don't
have it"), plus alternatives only if they really fit - never a book from the model's memory.
The set lives in Langfuse as a dataset, so every experiment runs on exactly the same items.
"""

DATASET_NAME = "book-recommender-12"

# (id, question, type, what a good answer does)
TEST_QUESTIONS = [
    ("q01", "أريد رواية تاريخية", "normal",
     "Recommends catalog novels with a historical theme, or says honestly that matches are weak."),
    ("q02", "أبحث عن كتاب يساعدني في تربية أطفالي", "normal",
     "Recommends parenting and family books from the catalog."),
    ("q03", "أريد كتاباً مبسطاً عن الفلسفة", "normal",
     "Recommends accessible philosophy books from the catalog."),
    ("q04", "كتاب عن الاقتصاد أو إدارة الأعمال", "normal",
     "Recommends economics or business books from the catalog."),
    ("q05", "أريد أن أفهم السياسة في العالم العربي", "normal",
     "Recommends politics books about the Arab world from the catalog."),
    ("q06", "كتاب علمي عن الطبيعة أو الكون", "normal",
     "Recommends science or nature books from the catalog."),
    ("q07", "أحب قراءة السير الذاتية والمذكرات", "normal",
     "Recommends biographies or memoirs from the catalog."),
    ("q08", "كتاب عن الفن أو الخط العربي", "normal",
     "Recommends art or Arabic calligraphy books from the catalog."),
    ("q09", "أريد كتاباً عن السيرة النبوية", "normal",
     "Recommends Islamic books about the Prophet's biography from the catalog, if any exist."),
    ("t01", "هل عندكم رواية هاري بوتر؟", "trap",
     "Says Harry Potter is not in the catalog. Recommends no invented books."),
    ("t02", "رشح لي روايات لنجيب محفوظ", "trap",
     "Says there are no Naguib Mahfouz novels in the catalog. Never lists his novels from memory."),
    ("t03", "أريد كتاباً لتعلم البرمجة بلغة بايثون", "trap",
     "Says the catalog has no programming books. Does not pad the answer with unrelated books."),
]


def sync_dataset(langfuse):
    """Create the Langfuse dataset once and upsert the 12 items by id (safe to re-run)."""
    try:
        langfuse.get_dataset(DATASET_NAME)
    except Exception:
        langfuse.create_dataset(
            name=DATASET_NAME,
            description="12 fixed reader questions: 9 normal + 3 traps (books we do not have)",
        )
    for item_id, question, kind, expected in TEST_QUESTIONS:
        langfuse.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=f"{DATASET_NAME}-{item_id}",
            input={"question": question},
            expected_output=expected,
            metadata={"type": kind},
        )
    return langfuse.get_dataset(DATASET_NAME)
