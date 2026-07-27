from __future__ import annotations


def extract_metadata_regex(pdf_text: str) -> dict:
    """
    Best-effort metadata extraction from raw PDF text using regex patterns.
    Used as a fallback when the LLM call fails or returns incomplete data.
    Tuned against Nature Communications / high-impact journal PDF structure.
    """
    import re as _re

    # Normalize whitespace — PDF line-wrapping splits phrases like
    # "25 pancreatic ductal adenocarcinoma (PDAC)\npatients" across lines,
    # breaking numeric patterns. Collapse all whitespace to single spaces.
    pdf_text_norm = _re.sub(r"\s+", " ", pdf_text)

    def _first(patterns, text, default=""):
        for pat in patterns:
            m = _re.search(pat, text, _re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return default

    def _find_int(patterns, text, default="?"):
        for pat in patterns:
            m = _re.search(pat, text, _re.IGNORECASE)
            if m:
                for g in m.groups():
                    if g and _re.search(r"\d", g):
                        return g.strip()
        return default

    # ── Title detection: try multiple strategies ─────────────────────────
    title = "Study Title Not Detected"

    # Strategy 1: lines before first author block (typical journal layout)
    # Article title usually appears in all-caps or title-case before author names
    title_candidates = []
    for l in pdf_text.splitlines()[:60]:   # first 60 lines of PDF text
        l = l.strip()
        if not l or len(l) < 15:
            continue
        # Skip journal name lines (all caps, short)
        if l.isupper() and len(l) < 30:
            continue
        # Skip lines that look like author lists (contains superscript-style digits)
        if _re.search(r"[A-Z][a-z]+[,\d]", l):
            continue
        # Skip DOI lines, page numbers, volume info
        if _re.search(r"10\.\d{4,}/|doi\.org|^\d+$|\bVol\b|\bDOI\b", l, _re.I):
            continue
        # A title-like line: 20-300 chars, contains meaningful words
        if 20 < len(l) < 300 and any(w in l.lower() for w in
           ["genomic","transcriptom","landscape","characteriz","sequenc","mutati","cancer",
            "tumor","tumour","invasion","pathway","single-cell","spatial","clinical","integrat",
            "molecular","expression","profiling","analysis","identifies","reveals","uncover"]):
            # Stop at citation-style lines (author list, volume/page)
            if _re.search(r"\b(20\d{2})\b.*\d+[,–-]\d+|et al\.|\bVol\.?\s*\d+\b", l):
                break
            title_candidates.append(l)
            if len(title_candidates) >= 3:
                break

    if title_candidates:
        # Join multi-line titles, cap at 200 chars
        title = " ".join(title_candidates)[:200]

    # Strategy 2: look after DOI line (some journals print title after DOI)
    _doi_match_title = _re.search(r"10\.[0-9]{4,}/\S+", pdf_text)
    if title == "Study Title Not Detected":
        doi_match = _doi_match_title
        if doi_match:
            after_doi = pdf_text[doi_match.end():]
            title_lines = []
            for l in after_doi.splitlines():
                l = l.strip()
                if not l:
                    continue
                if _re.search(r"[A-Z][a-z]+\d", l):
                    break
                if len(l) > 5:
                    title_lines.append(l)
                if len(title_lines) >= 3:
                    break
            if title_lines:
                title = " ".join(title_lines)

    # Strategy 3: any line that looks like a title
    if title == "Study Title Not Detected":
        for l in pdf_text.splitlines():
            l = l.strip()
            if 20 < len(l) < 200 and any(w in l.lower() for w in
               ["genomic","transcriptom","landscape","characteriz","sequenc","mutati","cancer","tumor","tumour"]):
                title = l
                break

    # ── DOI ───────────────────────────────────────────────────────────────
    doi = _first([
        r"https?://doi\.org/([^\s,;)]+)",
        r"(?:doi|DOI)[:\s]+([10]\.[0-9]{4,}/\S+)",
        r"\b(10\.[0-9]{4,}/[^\s,;)\]]+)",
    ], pdf_text).rstrip(".,;)")

    # ── PMID ──────────────────────────────────────────────────────────────
    pmid = _first([
        r"PMID[:\s]+(\d{6,9})",
        r"pubmed\.ncbi\.nlm\.nih\.gov/(\d{6,9})",
    ], pdf_text)

    # ── Year: prefer Accepted > Published > Received ──────────────────────
    year = (_first([r"Accepted[:\s]+\d+\s+\w+\s+(\d{4})"], pdf_text) or
            _first([r"Published[:\s]+\d+\s+\w+\s+(\d{4})",
                    r"Published online[:\s]+(\d{4})"], pdf_text) or
            _first([r"Received[:\s]+\d+\s+\w+\s+(\d{4})"], pdf_text) or
            _first([r"\b(20[12][0-9])\b"], pdf_text))

    # ── Journal ───────────────────────────────────────────────────────────
    journal = _first([
        r"(Nature Communications)",
        r"(Nature\s+(?:Genetics|Medicine|Cancer|Methods|Biotechnology|Chemical Biology|Cell Biology|Immunology))",
        r"(Nature\s+\w+)",
        r"(Cancer\s+(?:Cell|Discovery|Research|Medicine))",
        r"(Cell\s+(?:Genomics|Systems|Reports|Research|Host|Stem))",
        r"(Science\s+(?:Translational|Advances|Medicine))",
        r"(Clinical\s+Cancer\s+Research)",
        r"(Journal\s+of\s+Clinical\s+Oncology)",
        r"(Genome\s+(?:Research|Biology|Medicine))",
        r"(Blood\s+Cancer\s+Journal)",
        r"(Leukemia)",
        r"(\bNEJM\b|New England Journal)",
    ], pdf_text)

    # ── First author surname ─────────────────────────────────────────────
    # Strategy: find author list line after title (right after DOI), extract
    # the SURNAME of the first author.  Author lines look like:
    #   "Feifei Xie1,10,S h u z h e n..."  or  "Smith J1, Jones A2, ..."
    author = ""
    if _doi_match_title:
        after_doi = pdf_text[_doi_match_title.end():]
        for l in after_doi.splitlines():
            l = l.strip()
            if not l:
                continue
            # Pattern 1: "Firstname Surname[digit]" — e.g. "Feifei Xie1,10,"
            am = _re.match(r"[A-Z][a-z]+\s+([A-Z][a-z]+)\d", l)
            if am:
                author = am.group(1)
                break
            # Pattern 2: "Surname, Initials" style — "Smith J1,"
            am2 = _re.match(r"([A-Z][a-z]{1,15}),\s*[A-Z]\.?\s*\d", l)
            if am2:
                author = am2.group(1)
                break
            # Stop if we've passed the author block (abstract/intro begins)
            if len(l) > 150 or _re.match(r"[A-Z][a-z].{80,}", l):
                break
    # Fallback: "Surname et al." anywhere in text
    if not author:
        m = _re.search(r"([A-Z][a-z]{2,15})\s+et\s+al", pdf_text[:3000])
        if m:
            author = m.group(1)

    # ── Reference genome ──────────────────────────────────────────────────
    genome = _first([
        r"\b(hg38|GRCh38)\b",
        r"\b(hg19|GRCh37)\b",
        r"aligned\s+to\s+(hg\d+|GRCh\d+)",
        r"reference\s+genome[:\s]+(hg\d+|GRCh\d+)",
        r"mapped\s+to\s+(hg\d+|GRCh\d+)",
        r"NCBI\s+[Bb]uild\s+(37|38)",
    ], pdf_text)
    if genome:
        genome = (genome
                  .replace("GRCh38","hg38").replace("GRCh37","hg19")
                  .replace("38","hg38").replace("37","hg19"))
        # Normalise aliases
        if genome not in ("hg19","hg38"):
            genome = "hg38"
    else:
        # Cannot determine from text — leave blank so the LLM or user can fill in
        genome = ""

    # ── Sample / patient counts ───────────────────────────────────────────
    # NOTE: specific patterns FIRST — generic "(\d+) patients?" last to avoid
    # matching subgroup sizes (e.g. "8 patients in low-NI group")
    n_samples = _find_int([
        r"collected\s+(\d+)\s+samples?",                        # "collected 62 samples"
        r"(\d+)\s+samples?,?\s+including",                      # "62 samples, including"
        r"(\d+)\s+samples?\s+from\s+\d+\s+patients?",        # "62 samples from 25 patients"
        r"sc/snRNA-?seq\s+on\s+(\d+)\s+samples?",
        r"(\d+)\s+(?:fresh|ffpe|tissue|tumor|tumour|cancer|primary)\s+samples?",
        r"n\s*=\s*(\d+)\s*(?:samples?|specimens?)",
        r"(\d+)\s+samples?\s+(?:were|from|across|in|with)",
        r"(?:total\s+of\s+)?(\d{2,4})\s+samples?",
        r"(\d+)\s+GISTs?\b",
        r"(\d+)\s+(?:tumor|tumour)\s+(?:specimens?|biopsies|cases)",
    ], pdf_text_norm)
    n_patients = _find_int([
        r"(\d+)\s+treatment[- ]naive\s+patients?",              # "25 treatment-naive patients"
        r"collected\s+\d+\s+samples?.*?from\s+(\d+)\s+patients?",  # "62 samples from 25 patients"
        r"(\d+)\s+patients?\s+(?:diagnosed|enrolled|recruited|included|underwent)",
        r"N\s*=\s*(\d+)\s*patients?",                          # N=25 patients
        r"total\s+of\s+(\d+)\s+patients?",
        r"cohort\s+of\s+(\d+)\s+patients?",
        r"(\d+)\s+(?:individuals?|subjects?|donors?)",
        r"(\d+)\s+cases?\b",
        r"(\d+)\s+patients?",                                    # generic LAST
    ], pdf_text_norm)

    # ── Sequencing types ──────────────────────────────────────────────────
    seq_types = []
    for label, patterns in [
        ("WES",       [r"\bWES\b", r"whole[- ]exome\s+seq"]),
        ("WGS",       [r"\bWGS\b", r"whole[- ]genome\s+seq"]),
        ("WTS",       [r"\bWTS\b", r"whole[- ]transcriptome\s+seq"]),
        ("RNA-seq",   [r"\bRNA-?seq\b"]),
        ("scRNA-seq", [r"\bscRNA-?seq\b", r"single[- ]cell\s+RNA"]),
        ("snRNA-seq", [r"\bsnRNA-?seq\b", r"single[- ]nucleus\s+RNA"]),
        ("scTCR-seq", [r"\bscTCR-?seq\b", r"single[- ]cell\s+TCR"]),
        ("Spatial",   [r"\bspatial\s+transcriptom", r"\bVisium\b", r"\bSTAR-?map\b"]),
        ("ChIP-seq",  [r"\bChIP-?seq\b"]),
        ("ATAC-seq",  [r"\bATAC-?seq\b"]),
        ("targeted",  [r"targeted\s+(?:sequencing|panel|NGS)"]),
    ]:
        if any(_re.search(p, pdf_text, _re.IGNORECASE) for p in patterns):
            seq_types.append(label)

    # ── Cancer type ───────────────────────────────────────────────────────
    cancer_map = [
        (r"\bGIST\b|gastrointestinal\s+stromal",     "gist",  "Gastrointestinal Stromal Tumor"),
        (r"\bbreast\s+cancer\b|\bBRCA\b",           "brca",  "Breast Invasive Carcinoma"),
        (r"\blung\s+adenocarcinoma\b|\bLUAD\b",     "luad",  "Lung Adenocarcinoma"),
        (r"\blung\s+squamous\b|\bLUSC\b",           "lusc",  "Lung Squamous Cell Carcinoma"),
        (r"\bnon-small\s+cell\s+lung\b|\bNSCLC\b", "nsclc", "Non-Small Cell Lung Cancer"),
        (r"\blung\s+cancer\b",                        "luad",  "Lung Cancer"),
        (r"\bcolorectal\b|\bCRC\b|\bCOAD\b",       "coad",  "Colorectal Adenocarcinoma"),
        (r"\bglioblastoma\b|\bGBM\b",                "gbm",   "Glioblastoma Multiforme"),
        (r"\bglioma\b",                                "lgggbm","Glioma"),
        (r"\bmelanoma\b|\bSKCM\b",                   "skcm",  "Skin Cutaneous Melanoma"),
        (r"\bpancreatic\s+(?:cancer|ductal|adenocarcinoma)\b|\bPAAD\b", "paad", "Pancreatic Adenocarcinoma"),
        (r"\bprostate\s+cancer\b|\bPRAD\b",         "prad",  "Prostate Adenocarcinoma"),
        (r"\bovarian\s+(?:cancer|carcinoma)\b|\bOV\b", "ov", "Ovarian Serous Cystadenocarcinoma"),
        (r"\bhepat\w+\s+(?:carcinoma|cancer)\b|\bHCC\b", "hcc", "Hepatocellular Carcinoma"),
        (r"\bgastric\s+(?:cancer|carcinoma)\b|\bSTAD\b", "stad", "Stomach Adenocarcinoma"),
        (r"\bladder\s+(?:cancer|carcinoma)\b|\bBLCA\b", "blca", "Bladder Urothelial Carcinoma"),
        (r"\bacute\s+myeloid\s+leukemia\b|\bAML\b", "aml", "Acute Myeloid Leukemia"),
        (r"\bchronic\s+lymphocytic\s+leukemia\b|\bCLL\b", "cll", "Chronic Lymphocytic Leukemia"),
        (r"\bleukemia\b",                              "leuk",  "Leukemia"),
        (r"\blymphoma\b|\bDLBCL\b",                  "dlbcl", "Diffuse Large B-Cell Lymphoma"),
        (r"\bmultiple\s+myeloma\b|\bMM\b",          "mm",    "Multiple Myeloma"),
        (r"\brenal\s+(?:cell\s+carcinoma|cancer)\b|\bRCC\b|\bKIRC\b", "kirc", "Renal Clear Cell Carcinoma"),
        (r"\bthyroid\s+(?:cancer|carcinoma)\b|\bTHCA\b", "thca", "Thyroid Carcinoma"),
        (r"\bendometrial\b|\buterine\b|\bUCEC\b",  "ucec",  "Uterine Corpus Endometrial Carcinoma"),
        (r"\bsarcoma\b",                               "sarc",  "Sarcoma"),
        (r"\bmesothelioma\b|\bMESO\b",               "meso",  "Mesothelioma"),
        (r"\bcervical\b|\bCESC\b",                   "cesc",  "Cervical Squamous Cell Carcinoma"),
        (r"\bhead\s+and\s+neck\b|\bHNSC\b",        "hnsc",  "Head and Neck Squamous Cell Carcinoma"),
    ]
    cancer_t, cancer_full = "mixed", "Mixed Cancer Type"
    for pat, ct, cf in cancer_map:
        if _re.search(pat, pdf_text[:3000], _re.IGNORECASE):
            cancer_t, cancer_full = ct, cf
            break

    study_id = f"{cancer_t}_{author.lower()}_{year}" if author and year else f"{cancer_t}_study_{year or '2024'}"
    study_id = _re.sub(r"[^a-z0-9_]", "_", study_id).strip("_")

    # ── Data repositories ─────────────────────────────────────────────────
    repos = []
    for pat in [r"(GSE\d{5,7})", r"(EGAS\d{11})", r"(phs\d{6,7})",
                r"(HRA\d{6})", r"(PRJNA\d+)", r"(SRP\d+)",
                r"(ERP\d+)", r"dbGaP\s+accession[:\s]+(\S+)"]:
        for m in _re.finditer(pat, pdf_text, _re.IGNORECASE):
            v = m.group(1).strip()
            if v not in repos:
                repos.append(v)

    # ── Corresponding author ──────────────────────────────────────────────
    corresp = _first([
        r"[Cc]orresponding\s+authors?[:\s]+([^\n]{10,100})",
        r"[Cc]orrespondence[:\s]+([^\n]{10,100})",
        r"\*?[Ee]-mail[:\s]+([^\n]{10,80})",
    ], pdf_text)

    # ── Key findings ──────────────────────────────────────────────────────
    # Try to extract sentences with result-indicating words
    key_findings = []
    for sent in _re.split(r"[.!?]\s+", pdf_text[:4000]):
        sent = sent.strip()
        if (len(sent) > 40 and
            any(w in sent.lower() for w in ["identified","revealed","found","discover",
               "demonstrate","show","report","novel","significant","recurrent"]) and
            len(key_findings) < 5):
            key_findings.append(sent[:150])

    # ── Build description ─────────────────────────────────────────────────
    seq_str = "/".join(seq_types[:3]) if seq_types else "genomic"
    n_str   = f" of {n_samples} samples" if n_samples != "?" else ""
    desc    = f"{seq_str.upper()} characterization{n_str} of {cancer_full}."
    if author and journal and year:
        desc = f"{seq_str} study{n_str} of {cancer_full}. Published in {journal} ({year})."

    return {
        "study_title":          title[:200],
        "cancer_type":          cancer_t,
        "cancer_type_full":     cancer_full,
        "num_samples":          n_samples,
        "num_patients":         n_patients,
        "reference_genome":     genome,
        "sequencing_types":     seq_types,
        "pmid":                 pmid,
        "doi":                  doi,
        "first_author_surname": author,
        "year":                 year,
        "journal":              journal,
        "study_id_suggestion":  study_id,
        "description":          desc,
        "meta_description":     desc[:200],
        "key_findings":         key_findings,
        "primary_site":         "",
        "cohort_description":   (f"{n_patients} patients, {n_samples} samples."
                                  if n_patients != "?" else ""),
        "data_repositories":    repos[:4],
        "corresponding_authors": corresp,
    }


__all__ = ["extract_metadata_regex"]
