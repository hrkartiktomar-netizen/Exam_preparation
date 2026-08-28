"""Build question_banks/SEBI_All_Questions.md from md_sebi OCR files,
following the IFSCA_All_Questions.md pattern (Q#, options (a)-(e), > **Answer:**, > **Hint:**)."""
import os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "source_documents", "md_sebi")
OUT = os.path.join(ROOT, "question_banks", "SEBI_All_Questions.md")

FILES = [
    ("2020 (Phase 1+2).md", "SEBI Grade A 2020 – Phase 1 & 2"),
    ("2022 (Phase 1+2).md", "SEBI Grade A 2022 – Phase 1 & 2"),
    ("2024 (Phase 1).md", "SEBI Grade A 2024 – Phase 1"),
    ("2024 (Phase 2).md", "SEBI Grade A 2024 – Phase 2"),
    ("2025(Phase 1+2).md", "SEBI Grade A 2025 – Phase 1 & 2"),
]

Q_RE = re.compile(r"^\*{0,2}Q(\d+)\s*[\.\)]\s*(.*)$")
OPT_RE = re.compile(r"^\(?([A-E])[\.\)]\s+(.*)$")
ANS_RE = re.compile(r"^\*{0,2}Answer:\s*\(?\s*([A-E])\s*\)?\s*\*{0,2}")
HDR_RE = re.compile(r"^#{1,4}\s+(.*)$")
SCOPE_RE = re.compile(r"^#\s+.*?(Phase\s*\d+)\s*[-–]?\s*(Paper\s*\d+)", re.I)
SCOPE_RE2 = re.compile(r"^(?:#+\s*)?(?:SEBI\s+Grade\s+A\s*\d{4}\s*)?(Phase\s*\d+)\s*[-–]\s*(Paper\s*\d+)", re.I)
NOISE_RE = re.compile(r"^(\*\[Page|---|\[logo|^\s*$|\| :---)")

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def clean_bold(s):
    return s.replace("**", "").strip()

def parse_file(path):
    lines = open(path, encoding="utf-8").read().split("\n")
    questions = []          # dicts: num, section, text, options, answer, hint
    keymap = {}             # (scope, norm_section, k) -> letter
    section = ""
    scope = ""
    in_key = False
    cur = None              # current question dict
    sec_counter = {}        # (scope, norm_section) -> count of questions

    def flush():
        nonlocal cur
        if cur is not None:
            questions.append(cur)
            cur = None

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        m_ans_key = re.search(r"Answer Key", line, re.I)
        if m_ans_key:
            in_key = True
            flush()
        sm2 = SCOPE_RE2.match(line.strip())
        if sm2 and "](" not in line and not re.search(r"Answer Key", line, re.I):
            scope = norm(sm2.group(1) + sm2.group(2))
        m = Q_RE.match(line)
        if m and not in_key:
            flush()
            section_q = norm(section)
            ck = (scope, section_q)
            sec_counter[ck] = sec_counter.get(ck, 0) + 1
            cur = {
                "num": int(m.group(1)),
                "section": section or "General",
                "nsec": section_q,
                "scope": scope,
                "k": sec_counter[ck],
                "text": clean_bold(m.group(2)),
                "options": [],
                "answer": None,
                "hint": [],
            }
            i += 1
            continue
        h = HDR_RE.match(line)
        if h:
            title = clean_bold(h.group(1))
            sm = SCOPE_RE.match(line)
            if sm:
                scope = norm(sm.group(1) + sm.group(2))
            if not re.search(r"answer key", title, re.I):
                in_key = False
            section = title
            flush()
            i += 1
            continue
        if line.startswith("|") and ("Question" in line and "Answer" in line):
            # header of a key table; parse following rows (tables may be split by page breaks)
            i += 1
            while i < len(lines):
                row = lines[i].strip()
                if row.startswith("|"):
                    i += 1
                    if ":---" in row:
                        continue
                    cells = [c.strip() for c in row.strip("|").split("|")]
                    for j in range(0, len(cells) - 1, 2):
                        qn, an = cells[j], cells[j + 1]
                        if qn.isdigit() and re.fullmatch(r"[A-E]", an):
                            keymap[(scope, norm(section), int(qn))] = an
                    continue
                if row.startswith("*[Page") or row.startswith("---") or row.startswith("[logo") or not row:
                    i += 1
                    continue
                break
            continue
        if cur is not None and not in_key:
            mo = OPT_RE.match(line)
            if mo and not line.startswith("(E) "):
                cur["options"].append((mo.group(1), clean_bold(mo.group(2))))
                i += 1
                continue
            ma = ANS_RE.match(line)
            if ma:
                cur["answer"] = ma.group(1)
                i += 1
                continue
            if cur["answer"] is not None and line.strip() and not NOISE_RE.match(line) and not Q_RE.match(line):
                cur["hint"].append(clean_bold(line))
                i += 1
                continue
            if NOISE_RE.match(line) and not line.strip():
                i += 1
                continue
        i += 1
    flush()
    for q in questions:
        if q["answer"] is None:
            q["answer"] = keymap.get((q["scope"], q["nsec"], q["k"]))
    return questions

def guidebook_outline(path):
    out = []
    for line in open(path, encoding="utf-8"):
        h = HDR_RE.match(line.rstrip())
        if h:
            t = clean_bold(h.group(1))
            if t and not t.startswith("SEBI Grade A Guidebook"):
                out.append(t)
    return out

parts = []
parts.append("# SEBI Grade A Officer – Previous Year Question Bank (Consolidated)\n")
parts.append("---\n")
parts.append("## Table of Contents\n")
toc = []
body = []
for fname, title in FILES:
    qs = parse_file(os.path.join(SRC, fname))
    toc.append(f"- [{title}](#{norm(title)}) — {len(qs)} questions")
    body.append(f"\n---\n\n## {title}\n")
    body.append(f"**Total Questions:** {len(qs)} | **Type:** Objective (MCQ) | **Source:** {fname} (OCR)\n")
    last_sec = None
    for q in qs:
        if q["section"] != last_sec:
            body.append(f"\n### {q['section']}\n")
            last_sec = q["section"]
        body.append(f"**Q{q['num']}.** {q['text']}\n")
        for letter, opt in q["options"]:
            body.append(f"- ({letter.lower()}) {opt}")
        body.append("")
        ans = q["answer"]
        body.append(f"> **Answer:** ({ans.lower()})" if ans else "> **Answer:** (—)")
        hint = " ".join(q["hint"]).strip()
        if hint:
            body.append(">")
            body.append(f"> **Hint:** {hint}")
        body.append("\n---\n")

gb = guidebook_outline(os.path.join(SRC, "SEBI Grade A Guidebook.md"))
toc.append("- [Appendix: SEBI Grade A Guidebook outline](#appendix-sebi-grade-a-guidebook-outline)")
body.append("\n---\n\n## Appendix: SEBI Grade A Guidebook outline\n")
body.append("Full guidebook text: `source_documents/md_sebi/SEBI Grade A Guidebook.md`. Chapter outline:\n")
for t in gb:
    body.append(f"- {t}")
body.append("")

md = "\n".join(parts + toc + ["\n"] + body)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(md + "\n")
print("wrote", OUT, len(md.splitlines()), "lines")
