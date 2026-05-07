"""
PEF Annex I – Text Coding Script
=================================
Codes sentences and bullet points as:
  - 'requirement'    → sentence contains 'shall'
  - 'recommendation' → sentence contains 'should'
  - 'optional'       → sentence contains 'may'

Bullet-point lists are handled according to the following rules:
  1. If the introducing sentence contains 'shall'/'should'/'may',
     each bullet point inherits that code.
  2. Else if the list is a decision tree (intro contains 'if', OR
     all bullets contain 'if'), code the whole list as one element.
  3. Else code each bullet point separately by its own verb.
"""

import re
import pandas as pd

# ── helpers ──────────────────────────────────────────────────────────────────


def detect_code(text: str) -> str | None:
    """Return the code for a piece of text, or None if uncoded."""
    t = text.lower()
    if "shall" in t:
        return "requirement"
    if "should" in t:
        return "recommendation"
    if " may " in t or t.endswith(" may") or t.startswith("may "):
        return "optional"
    return None


def is_bullet(line: str) -> bool:
    return line.startswith("* ")


def bullet_text(line: str) -> str:
    return line[2:].strip()


# ── main parsing ─────────────────────────────────────────────────────────────


def parse_file(path: str) -> pd.DataFrame:
    with open(path, encoding="utf-8") as f:
        raw_lines = f.readlines()

    lines = [l.rstrip("\n") for l in raw_lines]
    n = len(lines)

    records = []  # list of dicts that will become the DataFrame rows

    # We walk through the file collecting "blocks".
    # A block is either:
    #   • a plain sentence (possibly spanning one line), or
    #   • an intro sentence followed by one or more bullet lines.

    i = 0
    while i < n:
        line = lines[i].strip()

        # ── skip empty / markdown heading / figure / table lines ─────────────
        if (
            not line
            or line.startswith("#")
            or re.match(r"^(Figure|Table|Note\s*:)\b", line, re.I)
        ):
            i += 1
            continue

        # ── look-ahead: is this the start of a bullet-point list? ────────────
        # A list starts when the *next* non-empty line is a bullet.
        next_bullet_idx = None
        j = i + 1
        while j < n:
            nxt = lines[j].strip()
            if not nxt:
                j += 1
                continue
            if is_bullet(nxt):
                next_bullet_idx = j
            break

        if next_bullet_idx is not None:
            # ── BULLET LIST BLOCK ────────────────────────────────────────────
            intro_line_no = i + 1  # 1-based
            intro_text = line
            intro_code = detect_code(intro_text)

            # collect all consecutive bullet lines (skip blank lines between)
            bullets = []  # list of (line_no_1based, text)
            k = next_bullet_idx
            while k < n:
                bl = lines[k].strip()
                if not bl:
                    k += 1
                    continue
                if is_bullet(bl):
                    bullets.append((k + 1, bullet_text(bl)))
                    k += 1
                else:
                    break

            # Determine how to code the block
            intro_lower = intro_text.lower()

            if intro_code:
                # Rule 1 – intro verb governs all bullets
                for b_lineno, b_text in bullets:
                    records.append(
                        dict(
                            line_number=b_lineno,
                            code=intro_code,
                            text=b_text,
                            context=intro_text,
                        )
                    )

            elif (
                "if " in intro_lower
                or " if " in intro_lower
                or all("if " in bt.lower() for _, bt in bullets)
            ):
                # Rule 2 – decision tree → single record for the whole list
                combined = intro_text + " " + " | ".join(bt for _, bt in bullets)
                records.append(
                    dict(
                        line_number=intro_line_no,
                        code=detect_code(combined) or "uncoded",
                        text=combined,
                        context=intro_text,
                    )
                )

            else:
                # Rule 3 – code each bullet by its own verb
                for b_lineno, b_text in bullets:
                    b_code = detect_code(b_text) or "uncoded"
                    records.append(
                        dict(
                            line_number=b_lineno,
                            code=b_code,
                            text=b_text,
                            context=intro_text,
                        )
                    )

            # advance past the bullet block
            i = k

        else:
            # ── PLAIN SENTENCE ───────────────────────────────────────────────
            code = detect_code(line)
            if code:
                # context = the sentence on the preceding non-empty/non-heading line
                context = ""
                ci = i - 1
                while ci >= 0:
                    prev = lines[ci].strip()
                    if prev and not prev.startswith("#"):
                        context = prev
                        break
                    ci -= 1

                records.append(
                    dict(
                        line_number=i + 1,
                        code=code,
                        text=line,
                        context=context,
                    )
                )
            i += 1

    df = pd.DataFrame(records, columns=["line_number", "code", "text", "context"])
    return df[df["code"] != "uncoded"]


# ── run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    INPUT_FILE = "text_coding/pef_annex1.txt"
    OUTPUT_CSV = "text_coding/pef_coded.csv"
    OUTPUT_XLSX = "text_coding/pef_coded.xlsx"

    df = parse_file(INPUT_FILE)

    # ── summary ──────────────────────────────────────────────────────────────
    print(f"Total coded items : {len(df)}")
    print(df["code"].value_counts().to_string())
    print()
    print(df.head(10).to_string(index=False))

    # ── save ─────────────────────────────────────────────────────────────────
    df.to_csv(OUTPUT_CSV, index=False)
    df.to_excel(OUTPUT_XLSX, index=False)
    print(f"\nSaved CSV  → {OUTPUT_CSV}")
    print(f"Saved XLSX → {OUTPUT_XLSX}")
