"""Drug-name and reaction-term normalisation.

FAERS drug names are free text (brands, salts, dosage forms, typos).  For
disproportionality analysis we need stable canonical names.  Strategy:

1. exact brand -> generic alias map (curated, common high-volume drugs),
2. strip dosage-form / salt / strength tokens,
3. collapse whitespace, drop junk placeholders.

This is intentionally transparent and auditable — no black-box fuzzy magic.
"""
from __future__ import annotations

import re

# Curated brand -> generic map covering many high-volume FAERS brands.
BRAND_TO_GENERIC = {
    "TYLENOL": "ACETAMINOPHEN", "ADVIL": "IBUPROFEN", "MOTRIN": "IBUPROFEN",
    "ALEVE": "NAPROXEN", "ASPIRIN": "ASPIRIN", "PLAVIX": "CLOPIDOGREL",
    "COUMADIN": "WARFARIN", "ELIQUIS": "APIXABAN", "XARELTO": "RIVAROXABAN",
    "PRADAXA": "DABIGATRAN", "PROZAC": "FLUOXETINE", "ZOLOFT": "SERTRALINE",
    "PAXIL": "PAROXETINE", "CELEXA": "CITALOPRAM", "LEXAPRO": "ESCITALOPRAM",
    "EFFEXOR": "VENLAFAXINE", "WELLBUTRIN": "BUPROPION", "LAMICTAL": "LAMOTRIGINE",
    "DEPAKOTE": "VALPROIC ACID", "TEGRETOL": "CARBAMAZEPINE", "LYRICA": "PREGABALIN",
    "NEURONTIN": "GABAPENTIN", "LIPIITOR": "ATORVASTATIN", "ZOCOR": "SIMVASTATIN",
    "CRESTOR": "ROSUVASTATIN", "PRAVACHOL": "PRAVASTATIN", "LESCOL": "FLUVASTATIN",
    "GLUCOPHAGE": "METFORMIN", "JANUVIA": "SITAGLIPTIN", "GLYBURIDE": "GLYBURIDE",
    "AMBRISENT": "PIOGLITAZONE", "VICTOZA": "LIRAGLUTIDE", "TRULICITY": "DULAGLUTIDE",
    "HUMALOG": "INSULIN LISPRO", "LANTUS": "INSULIN GLARGINE", "NOVOLOG": "INSULIN ASPART",
    "LEVEMIR": "INSULIN DETEMIR", "PRANDIN": "REPAGLINIDE", "STARGLIX": "GLYMEPIRIDE",
    "VENTOLIN": "ALBUTEROL", "PROAIR": "ALBUTEROL", "SINGULAIR": "MONTELUKAST",
    "ADVAIR": "FLUTICASONE-SALMETEROL", "BREO": "FLUTICASONE-VILANTEROL",
    "SPIRIVA": "TIOTROPIUM", "XOLAIR": "OMALIZUMAB", "HUMIRA": "ADALIMUMAB",
    "REMICADE": "INFLIXIMAB", "ENBREL": "ETANERCEPT", "YTELVI": "USTEKINUMAB",
    "KEYTRUDA": "PEMBROLIZUMAB", "OPDIVO": "NIVOLUMAB", "TECENTRIQ": "ATEZOLIZUMAB",
    "ARICEPT": "DONEPEZIL", "EXELON": "RIVASTIGMINE", "NAMENDA": "MEMANTINE",
    "EYLEA": "AFLIBERCEPT", "AVASTIN": "BEVACIZUMAB", "HERCEPTIN": "TRASTUZUMAB",
    "TAXOTERE": "DOCETAXEL", "TAXTOL": "PACLITAXEL", "Xeloda": "CAPECITABINE",
    "TECFIDERA": "DIMETHYL FUMARATE", "AUBAGIO": "TERIFLUNOMIDE",
    "TYSABRI": "NATALIZUMAB", "OCREVUS": "OCRELIZUMAB", "METHOTREXATE": "METHOTREXATE",
    "PREDNISONE": "PREDNISONE", "MOTILIUM": "DOMPERIDONE", "ZANTAC": "RANITIDINE",
    "NEXIUM": "ESOMEPRAZOLE", "PRILOSEC": "OMEPRAZOLE", "PROTONIX": "PANTOPRAZOLE",
    "CARDIZEM": "DILTIAZEM", "LOPRESSOR": "METOPROLOL", "TOPROL": "METOPROLOL",
    "LIPITOR": "ATORVASTATIN",
    "COZAAR": "LOSARTAN", "AVAPRO": "IRBESARTAN", "NORVASC": "AMLODIPINE",
    "ZESTRIL": "LISINOPRIL", "ALTACE": "RAMIPRIL", "VASOTEC": "ENALAPRIL",
    "LASIX": "FUROSEMIDE", "CLONIDINE": "CLONIDINE", "THYROID": "LEVOTHYROXINE",
    "SYNTHROID": "LEVOTHYROXINE", "ELTROXIN": "LEVOTHYROXINE",
    "XANAX": "ALPRAZOLAM", "VALIUM": "DIAZEPAM", "ATIVAN": "LORAZEPAM",
    "KLONOPIN": "CLONAZEPAM", "AMBIEN": "ZOLPIDEM", "SONATA": "ZALEPLON",
    "OXYCONTIN": "OXYCODONE", "VICODIN": "HYDROCODONE", "DILAUDID": "HYDROMORPHONE",
    "PERCOCET": "OXYCODONE-ACETAMINOPHEN", "FENTANYL": "FENTANYL",
    "RITALIN": "METHYLPHENIDATE", "ADDERALL": "AMPHETAMINE",
    "SEROQUEL": "QUETIAPINE", "ABILIFY": "ARIPIPRAZOLE", "ZYPREXA": "OLANZAPINE",
    "RISPERDAL": "RISPERIDONE", "GEODON": "ZIPRASIDONE", "LATUDA": "LURASIDONE",
    "ELAVIL": "AMITRIPTYLINE", "PAMELOR": "NORTRIPTYLINE", "SINEQUAN": "DOXEPIN",
    "BENADRYL": "DIPHENHYDRAMINE", "Zyrtec": "CETIRIZINE", "CLARITIN": "LORATADINE",
    "ALLEGRA": "FEXOFENADINE", "EPIPen": "EPINEPHRINE",
    "ROCEFTRIAXONE": "CEFTRIAXONE", "ZITHROMAX": "AZITHROMYCIN",
    "CLEOCIN": "CLINDAMYCIN", "BACTRIM": "TRIMETHOPRIM-SULFAMETHOXAZOLE",
    "CIPRO": "CIPROFLOXACIN", "LEVAQUIN": "LEVOFLOXACIN", "FLAGYL": "METRONIDAZOLE",
    "VANCOCIN": "VANCOMYCIN", "MONUROL": "FOSFOMYCIN",
    "TAMIFLU": "OSELTAMIVIR", "RELENZA": "ZANAMIVIR",
    "HEPARIN": "HEPARIN", "LOVENOX": "ENOXAPARIN", "ELEQUIS": "APIXABAN",
    "ZOLGENSMA": "ONASEMNOGEN ABEVOVEC", "SPINRAZA": "NUSINERSEN",
}

# Tokens removed from drug names (dosage forms, strengths, salts, schedule words).
DROP_TOKENS = {
    "TABLET", "TABLETS", "CAPSULE", "CAPSULES", "CAP", "CAPS", "TAB", "TABS",
    "ORAL", "SOLUTION", "SUSPENSION", "INJECTION", "INJ", "SYRUP", "CREAM",
    "OINTMENT", "GEL", "PATCH", "PATCHES", "DROPS", "INHALER", "SPRAY",
    "POWDER", "GRANULES", "EFFERVESCENT", "SUBLINGUAL", "TRANSDERMAL",
    "RECTAL", "TOPICAL", "OPHTHALMIC", "OTIC", "NASAL", "VAGINAL",
    "FORTE", "PLUS", "XR", "XL", "SR", "ER", "CR", "LA", "DR", "EC",
    "EXTRA", "STRENGTH", "REGULAR", "ULTRA", "MAX", "MAXIMUM", "TOTAL",
    "ORIGINAL", "EVERYDAY", "LIQUI", "GELS", "SOFTGELS", "GELTABS",
    "HCL", "HYDROCHLORIDE", "HBR", "HYDROBROMIDE", "SODIUM", "POTASSIUM",
    "CALCIUM", "MALEATE", "BITARTRATE", "TARTRATE", "SULFATE", "SULPHATE",
    "PHOSPHATE", "FUMARATE", "MESYLATE", "TOSYLATE", "ACETATE", "CITRATE",
    "GLUCONATE", "MONOHYDRATE", "DIHYDRATE", "TRIHYDRATE", "ANHYDROUS",
    "SUCCINATE", "BESYLATE", "VALERATE", "PROPIONATE", "ESTOLATE",
    "EMBONATE", "PAMOATE", "MICRONIZED", "COMPOUND", "DIETHANOLAMINE",
}

# Placeholder names that carry no analytic meaning.
JUNK_NAMES = {
    "", "UNKNOWN", "UNK", "NOT KNOWN", "NOT SPECIFIED", "NONE", "NA", "N/A",
    "NONE LISTED", "OTHER", "OTHER MEDICATION", "OTHER MEDICATIONS", "TEST",
    "NONE KNOWN", "NONE KNOWN.", "NOT APPLICABLE", "NONE LISTED.", ".", "-",
    "MULTIPLE", "SEVERAL", "MEDICATION", "DRUG", "HOMEOPATHIC MEDICINE",
    "AYURVEDIC MEDICINE", "CONCOMITANT MEDICATION",
}

_NUMBER_RE = re.compile(r"\b\d+(\.\d+)?\s*(MG|MCG|G|GM|ML|IU|UNITS?|%|%)?\b")
_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9\-\s/]")


def normalize_drug(name: str | None) -> str | None:
    """Canonicalise a verbatim drug name. Returns None for junk/unusable names."""
    if not name:
        return None
    raw = str(name).strip().upper()
    if raw in JUNK_NAMES:
        return None
    # remove parenthetical qualifiers and dose strengths
    raw = re.sub(r"\([^)]*\)", " ", raw)
    raw = _NUMBER_RE.sub(" ", raw)
    # brand map hit? (check full string, then token-wise)
    if raw in BRAND_TO_GENERIC:
        return BRAND_TO_GENERIC[raw]
    tokens = [t for t in _WS_RE.split(_NON_ALNUM_RE.sub(" ", raw)) if t]
    mapped = [BRAND_TO_GENERIC.get(t, t) for t in tokens]
    kept = [t for t in mapped if t not in DROP_TOKENS]
    if not kept:
        return None
    out = " ".join(kept)
    out = _WS_RE.sub(" ", out).strip()
    if not out or out in JUNK_NAMES:
        return None
    return out


def normalize_pt(pt: str | None) -> str | None:
    """Whitespace-clean a MedDRA preferred term (keep MedDRA casing)."""
    if not pt:
        return None
    out = _WS_RE.sub(" ", str(pt)).strip().rstrip(".").strip()
    return out or None


def display_name(canonical: str) -> str:
    """Title-case presentation form of a canonical drug name."""
    return canonical.title()
