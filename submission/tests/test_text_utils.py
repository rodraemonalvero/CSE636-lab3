from src.text_utils import is_palindrome, normalize_text, word_count


def test_normalize_text():
    assert normalize_text("  Hello   WORLD  ") == "hello world"


def test_word_count():
    assert word_count("one two three") == 3


def test_word_count_empty():
    assert word_count("   ") == 0


def test_is_palindrome():
    assert is_palindrome("A man, a plan, a canal: Panama")


def test_is_not_palindrome():
    assert not is_palindrome("DevOps")