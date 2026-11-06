from app.rag.retrieval import _any_word_query


def test_words_are_joined_with_or_and_deduplicated() -> None:
    assert _any_word_query(
        "What file format must figures be supplied as, figures?"
    ) == ("what or file or format or must or figures or be or supplied or as")


def test_punctuation_and_odd_input_are_neutralised() -> None:
    assert _any_word_query('a:b & (c) -d "e"') == "a or b or c or d or e"
    assert _any_word_query("???") == ""
