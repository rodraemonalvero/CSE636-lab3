"""Text utility functions used by the CI assignment."""


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def word_count(text: str) -> int:
    normalized=normalize_text(text)
    if not normalized:return 0
    return len(normalized.split())


def is_palindrome(text: str) -> bool:
    cleaned="".join(character.lower() for character in text if character.isalnum())
    return cleaned==cleaned[::-1]