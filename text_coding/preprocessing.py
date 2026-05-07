import re
from bs4 import BeautifulSoup, NavigableString

INPUT_PATH = "text_coding/pef_recommendation.html"
OUTPUT_PATH = "text_coding/pef_annex1.txt"


# ======================================================================
# 1. HTML extraction and cleaning
# ======================================================================
def extract_annex1_html(input_path: str = INPUT_PATH):
    """
    Load the EUR-Lex HTML file and return the raw HTML fragment
    corresponding to Annex I (from anchor tocId3 to tocId45).
    """
    with open(input_path, "r", encoding="utf-8") as f:
        html = f.read()

    start_marker = 'id="tocId3"'
    end_marker = 'id="tocId45"'

    start_pos = html.find(start_marker)
    end_pos = html.find(end_marker)

    if start_pos == -1 or end_pos == -1:
        raise ValueError(
            "Could not locate Annex I boundary anchors (tocId3 / tocId45). "
            "Check that the input file is the correct EUR-Lex HTML export."
        )

    return html[start_pos:end_pos]


def clean_and_convert(annex1_html: str) -> str:
    """
    Parse the Annex I HTML fragment, remove EUR-Lex presentational
    features, and convert to structured plain text with markdown-style
    heading prefixes.

    Cleaning steps:
      - Remove embedded table-of-contents tables (class 'toc-item')
      - Remove footnote paragraphs (class 'footnote')
      - Remove inline superscript footnote reference links

    Heading hierarchy:
      # : heading level 1
      ## : heading level 2
      ...
      ####### : heading level 7

    Tables (abbreviations, definitions, data tables) are rendered as
    tab-separated rows.
    """
    soup = BeautifulSoup(annex1_html, "html.parser")

    # Remove embedded TOC tables
    for table in soup.find_all("table"):
        table.decompose()

    # Remove footnote paragraphs
    for fn in soup.find_all("p", class_="footnote"):
        fn.decompose()

    # Remove inline superscript footnote reference links
    for a in soup.find_all("a", href=True):
        if a.get("href", "").startswith("#src.") or a.get("href", "").startswith("#E0"):
            a.decompose()

    for table_description in soup.find_all("p", class_="title-table"):
        table_description.decompose()

    # Heading class mappings
    H1 = {"title-annex-1"}
    H2 = {"title-annex-2"}
    H3 = {"title-annex-3"}
    H4 = {"title-gr-seq-level-1"}
    H5 = {"title-gr-seq-level-2"}
    H6 = {"title-gr-seq-level-3"}
    H7 = {"title-gr-seq-level-4"}

    def clean(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    output_lines = []
    visited = set()

    def process_node(node, list_depth=0):
        if id(node) in visited:
            return
        visited.add(id(node))

        if isinstance(node, NavigableString):
            return

        tag = node.name
        classes = set(node.get("class") or [])

        # List items: grid-container grid-list → "* text" / "** text" etc.
        if tag == "div" and "grid-container" in classes and "grid-list" in classes:
            prefix = "*" * (list_depth + 1)
            content_div = node.find("div", class_="grid-list-column-2")
            if content_div:
                if content_div.find("div", class_="grid-container"):
                    # Nested list: emit text children at current depth,
                    # recurse into nested grid-lists one level deeper
                    for child in content_div.children:
                        if not hasattr(child, "name") or not child.name:
                            continue
                        child_classes = set(child.get("class") or [])
                        if child.name == "p":
                            text = clean(child.get_text(" ", strip=True))
                            if text:
                                output_lines.append(f"{prefix} {text}")
                        elif "list" in child_classes and not child.find(
                            "div", class_="grid-container"
                        ):
                            # div.list containing only text (no nested grid-lists)
                            text = clean(child.get_text(" ", strip=True))
                            if text:
                                output_lines.append(f"{prefix} {text}")
                        else:
                            process_node(child, list_depth + 1)
                else:
                    content = clean(content_div.get_text(" ", strip=True))
                    if content:
                        output_lines.append(f"{prefix} {content}")
            return  # do not recurse further into list children

        # Paragraphs: apply heading markers or output as plain text
        if tag == "p":
            text = clean(node.get_text(" ", strip=True))
            if not text:
                return
            if classes & H1:
                output_lines.append(f"\n# {text}")
            elif classes & H2:
                output_lines.append(f"\n## {text}")
            elif classes & H3:
                output_lines.append(f"\n### {text}")
            elif classes & H4:
                output_lines.append(f"\n#### {text}")
            elif classes & H5:
                output_lines.append(f"\n##### {text}")
            elif classes & H6:
                output_lines.append(f"\n###### {text}")
            elif classes & H7:
                output_lines.append(f"\n####### {text}")
            elif "toc-item" in classes:
                pass  # skip residual TOC items
            else:
                output_lines.append(text)
            return

        # Recurse into all other elements
        for child in node.children:
            process_node(child, list_depth)

    for child in soup.children:
        process_node(child)

    full_text = "\n".join(output_lines)
    full_text = re.sub(r"\n{4,}", "\n\n\n", full_text)
    return full_text.strip()


# ======================================================================
# 2. Sentence splitting
# ======================================================================

# Common abbreviations that should not trigger a sentence boundary
ABBREVS = {
    "fig",
    "figs",
    "e.g",
    "i.e",
    "etc",
    "approx",
    "vs",
    "cf",
    "no",
    "vol",
    "eq",
    "sec",
    "ref",
    "refs",
    "pp",
    "p",
    "al",
    "dr",
    "mr",
    "mrs",
    "prof",
    "dept",
    "est",
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
    "inc",
    "ltd",
    "corp",
    "min",
    "max",
    "avg",
    "std",
    "co",
    "op",
    "art",
    "par",
    "annex",
}

HEADING_RE = re.compile(r"^(#{1,7} )")


def is_abbrev(text: str, period_pos: int) -> bool:
    """Return True if the period at period_pos follows a known abbreviation."""
    start = period_pos
    while start > 0 and text[start - 1].isalpha():
        start -= 1
    word = text[start:period_pos].lower()
    if word in ABBREVS:
        return True
    if len(word) == 1:  # single letter (e.g. section label "A.")
        return True
    return False


def split_sentences(text: str) -> list:
    """
    Split a string into sentences. A sentence boundary is identified
    when '.', '!' or '?' is followed by whitespace and an uppercase
    letter or opening punctuation, unless the period belongs to a
    known abbreviation.
    """
    sentences = []
    current = []
    i = 0
    while i < len(text):
        char = text[i]
        current.append(char)
        if char in ".!?":
            j = i + 1
            while j < len(text) and text[j] == " ":
                j += 1
            if j < len(text) and (text[j].isupper() or text[j] in "(\"'"):
                if not is_abbrev(text, i):
                    sentence = "".join(current).strip()
                    if sentence:
                        sentences.append(sentence)
                    current = []
        i += 1
    remainder = "".join(current).strip()
    if remainder:
        sentences.append(remainder)
    return sentences


def split_into_sentences(plain_text: str) -> str:
    """
    Process plain text line by line. Headings, delimiters, empty lines,
    and lines below the length threshold are kept intact. Longer lines
    are split into individual sentences, each placed on its own line.
    """
    output = []
    for line in plain_text.splitlines():
        stripped = line.rstrip()

        if not stripped or HEADING_RE.match(stripped):
            output.append(stripped)
            continue

        sentences = split_sentences(stripped)
        if len(sentences) <= 1:
            output.append(stripped)
        else:
            for sent in sentences:
                sent = sent.strip()
                if sent:
                    output.append(sent)

    result = "\n".join(output)
    result = re.sub(r"\n{4,}", "\n\n\n", result)
    return result.strip()


# ======================================================================
# 3. Entry point
# ======================================================================


def main():
    print("Extracting Annex I...")
    annex1_html = extract_annex1_html()

    print("Cleaning and converting to plain text...")
    plain_text = clean_and_convert(annex1_html)

    print("Splitting into sentences...")
    plain_text = split_into_sentences(plain_text)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(plain_text)

    print(f"Done.")
    print(f"  Characters : {len(plain_text):,}")
    print(f"  Lines      : {plain_text.count(chr(10)):,}")


if __name__ == "__main__":
    main()
