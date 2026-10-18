"""Patient-review analytics.

Transparent lexicon-based analysis of patient review text:

- rating statistics per drug (mean, low-rating share, histogram),
- side-effect severity mix (druglib categorical field),
- adverse-event term extraction via a curated, public-domain-style lexicon,
- positive/negative opinion word counting for a corroboration signal.

No black-box NLP: every extracted term maps back to an explicit lexicon entry
that is documented in the methodology page.
"""
from __future__ import annotations

import json
import re

import pandas as pd

# Common patient-reported adverse drug reactions (lay + medical wording).
ADR_TERMS = [
    "nausea", "vomiting", "diarrhea", "constipation", "dizziness", "drowsiness",
    "headache", "migraine", "fatigue", "insomnia", "anxiety", "depression",
    "irritability", "confusion", "memory loss", "rash", "hives", "itching",
    "hair loss", "weight gain", "weight loss", "appetite loss", "dry mouth",
    "blurred vision", "double vision", "palpitations", "shortness of breath",
    "chest pain", "swelling", "edema", "joint pain", "muscle pain", "muscle cramps",
    "weakness", "tingling", "numbness", "tremor", "seizure", "hallucinations",
    "suicidal", "bleeding", "bruising", "dry cough", "sore throat", "fever",
    "chills", "sweating", "hot flashes", "low libido", "erectile dysfunction",
    "dry skin", "acne", "heartburn", "stomach pain", "indigestion", "loss of taste",
    "kidney problems", "liver problems", "high blood pressure", "low blood sugar",
    "blood sugar", "urinary retention", "frequent urination", "back pain",
    "neck pain", "restlessness", "brain fog", "difficulty concentrating",
    "mood swings", "nightmares", "gas", "bloating", "hiccups", "leg cramps",
    "arm pain", "injection site", "hair thinning", "nail changes", "blistering",
    "dry eyes", "ringing in the ears", "ear pain", "sinus", "post nasal",
    "wheezing", "swollen gums", "taste change", "short term memory",
]

POS_WORDS = [
    "effective", "works", "worked", "relief", "relieved", "helped", "helpful",
    "great", "excellent", "amazing", "wonderful", "love", " life-changing",
    "improved", "improvement", "recommend", "recommended", "happy", "pleased",
    "best", "fast", "clear", "cured", "benefit", "positive", "comfort",
]
NEG_WORDS = [
    "terrible", "worst", "horrible", "useless", "worse", "painful", "suffering",
    "hated", "hate", "awful", "nightmare", "ruined", "poison", "failed",
    "ineffective", "did not work", "didnt work", "no relief", "agony",
    "regret", "stopped taking", "quit taking", "dangerous", "overrated",
]

_ADR_RE = {term: re.compile(r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b") for term in ADR_TERMS}
_POS_RE = [re.compile(r"\b" + w.strip() + r"\b") for w in POS_WORDS]
_NEG_RE = [re.compile(r"\b" + w.strip() + r"\b") for w in NEG_WORDS]


def extract_adr_terms(text: str) -> list[str]:
    low = (text or "").lower()
    return [term for term, rx in _ADR_RE.items() if rx.search(low)]


def _sentiment(text: str) -> str:
    low = (text or "").lower()
    pos = sum(1 for rx in _POS_RE if rx.search(low))
    neg = sum(1 for rx in _NEG_RE if rx.search(low))
    if neg > pos:
        return "neg"
    if pos > neg:
        return "pos"
    return "neu"


def compute_review_stats(reviews_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-drug stats DataFrame, per-drug rating histogram long-DF)."""
    if reviews_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = reviews_df.copy()
    df["adr_terms_list"] = df["review_text"].fillna("").map(extract_adr_terms)
    df["sentiment"] = df["review_text"].map(_sentiment)

    hist = (
        df.groupby(["drug_normalized", "rating"]).size().reset_index(name="count")
        if not df.empty else pd.DataFrame()
    )

    def _agg(group: pd.DataFrame) -> pd.Series:
        term_counter: dict[str, int] = {}
        for terms in group["adr_terms_list"]:
            for t in terms:
                term_counter[t] = term_counter.get(t, 0) + 1
        top_terms = sorted(term_counter.items(), key=lambda kv: -kv[1])[:8]
        sev = group["side_effect_severity"].dropna()
        severe_share = (sev == "Severe").mean() if len(sev) else 0.0
        return pd.Series(
            {
                "reviews": len(group),
                "mean_rating": round(group["rating"].mean(), 2) if group["rating"].notna().any() else None,
                "low_rating_share": round((group["rating"] <= 4).mean(), 4) if group["rating"].notna().any() else 0.0,
                "neg_share": round((group["sentiment"] == "neg").mean(), 4),
                "pos_share": round((group["sentiment"] == "pos").mean(), 4),
                "severe_share": round(float(severe_share), 4),
                "adr_terms": json.dumps([{"term": t, "count": c} for t, c in top_terms]),
            }
        )

    stats = df.groupby("drug_normalized").apply(_agg, include_groups=False).reset_index()
    return stats, hist
