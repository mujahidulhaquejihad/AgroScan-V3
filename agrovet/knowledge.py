"""Plant-disease knowledge base + a lightweight offline chatbot.

Powers:
  * treatment advice shown under the ensemble "best answer"
  * the /api/chat assistant (rule-based, works without any external LLM)
  * the /api/resources endpoint (emergency vet hotlines + govt links)

The advice is general agronomic guidance for Bangladeshi farmers and is not a
substitute for a qualified plant doctor / veterinarian.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .knowledge_bn import DISEASE_INFO_BN, SEVERITY_BN

# --------------------------------------------------------------------------- #
# Emergency contacts (Bangladesh) and government resources
# --------------------------------------------------------------------------- #
EMERGENCY_CONTACTS = [
    {
        "name": "Krishi Call Center (Agriculture Helpline)",
        "phone": "16123",
        "hours": "9am - 5pm, Sat-Thu",
        "note": "Free crop & plant disease advice from agriculture officers.",
    },
    {
        "name": "Department of Livestock Services (Vet Helpline)",
        "phone": "16358",
        "hours": "9am - 5pm",
        "note": "Livestock & veterinary emergencies.",
    },
    {
        "name": "National Emergency Service",
        "phone": "999",
        "hours": "24/7",
        "note": "General emergencies.",
    },
]

GOV_LINKS = [
    {
        "name": "Ministry of Agriculture",
        "abbr": "MoA",
        "url": "https://moa.gov.bd",
        "desc": "National policies, notices, subsidies and agricultural schemes.",
        "category": "ministry",
    },
    {
        "name": "Department of Agricultural Extension (DAE)",
        "abbr": "DAE",
        "url": "http://dae.gov.bd",
        "desc": "Field officers, farmer training and crop extension services nationwide.",
        "category": "extension",
    },
    {
        "name": "Bangladesh Agricultural Research Institute (BARI)",
        "abbr": "BARI",
        "url": "http://www.bari.gov.bd",
        "desc": "Crop research, improved varieties and farm technologies.",
        "category": "research",
    },
    {
        "name": "Bangladesh Rice Research Institute (BRRI)",
        "abbr": "BRRI",
        "url": "http://brri.gov.bd",
        "desc": "Rice varieties, cultivation guides and paddy research.",
        "category": "research",
    },
    {
        "name": "Department of Livestock Services (DLS)",
        "abbr": "DLS",
        "url": "http://dls.gov.bd",
        "desc": "Veterinary care, livestock programmes and animal health.",
        "category": "livestock",
    },
    {
        "name": "Bangladesh Agricultural Research Council (BARC)",
        "abbr": "BARC",
        "url": "http://www.barc.gov.bd",
        "desc": "Coordinates agricultural research across Bangladesh.",
        "category": "research",
    },
    {
        "name": "e-Krishi / Krishi Batayon",
        "abbr": "e-Krishi",
        "url": "http://krishi.gov.bd",
        "desc": "Digital portal for crop info, alerts and farmer services.",
        "category": "digital",
    },
    {
        "name": "Bangladesh Agricultural Development Corporation (BADC)",
        "abbr": "BADC",
        "url": "http://badc.gov.bd",
        "desc": "Seeds, fertiliser distribution and irrigation support.",
        "category": "inputs",
    },
]

# --------------------------------------------------------------------------- #
# Disease knowledge base (keyed by a normalized condition slug)
# --------------------------------------------------------------------------- #
DISEASE_INFO: Dict[str, Dict[str, object]] = {
    "healthy": {
        "title": "Healthy leaf",
        "summary": "No disease detected. The leaf looks healthy.",
        "symptoms": ["Uniform green colour", "No spots, mold or wilting"],
        "treatment": ["No treatment needed."],
        "prevention": ["Keep up balanced fertilisation and irrigation.", "Scout the field weekly for early symptoms."],
        "severity": "none",
    },
    "apple_scab": {
        "title": "Apple scab",
        "summary": "Fungal disease (Venturia inaequalis) causing olive-green to black velvety spots.",
        "symptoms": ["Olive-green/black spots on leaves", "Scabby, cracked fruit", "Early leaf drop"],
        "treatment": ["Apply protectant fungicides (e.g., mancozeb) or captan at green-tip and repeat per label.", "Prune to improve air flow."],
        "prevention": ["Rake and destroy fallen leaves", "Plant resistant varieties", "Avoid overhead irrigation"],
        "severity": "moderate",
    },
    "black_rot": {
        "title": "Black rot",
        "summary": "Fungal disease causing leaf spots ('frog-eye') and fruit rot.",
        "symptoms": ["Brown circular leaf spots with purple margins", "Rotting, shrivelled fruit", "Cankers on twigs"],
        "treatment": ["Remove mummified fruit and cankers", "Apply fungicide (captan/mancozeb) from bloom onward"],
        "prevention": ["Sanitation: remove infected wood & fruit", "Improve canopy airflow"],
        "severity": "moderate",
    },
    "rust": {
        "title": "Rust (incl. cedar-apple & common rust)",
        "summary": "Fungal disease producing orange/rusty pustules on leaves.",
        "symptoms": ["Yellow-orange spots on upper leaf", "Rusty pustules underneath", "Premature leaf drop"],
        "treatment": ["Apply fungicide at first sign (e.g., myclobutanil for cedar-apple rust)", "Remove nearby alternate hosts (junipers) where relevant"],
        "prevention": ["Use resistant varieties", "Avoid prolonged leaf wetness"],
        "severity": "moderate",
    },
    "powdery_mildew": {
        "title": "Powdery mildew",
        "summary": "White powdery fungal growth on leaf surfaces.",
        "symptoms": ["White/grey powder on leaves & shoots", "Distorted, stunted growth"],
        "treatment": ["Apply sulfur or potassium-bicarbonate sprays", "Use systemic fungicide for heavy infection"],
        "prevention": ["Improve airflow & sunlight", "Avoid excess nitrogen", "Plant resistant cultivars"],
        "severity": "moderate",
    },
    "gray_leaf_spot": {
        "title": "Gray leaf spot / Cercospora",
        "summary": "Fungal disease of maize causing rectangular grey-brown lesions.",
        "symptoms": ["Long rectangular tan/grey lesions along veins", "Lesions merge and blight the leaf"],
        "treatment": ["Apply foliar fungicide (strobilurin/triazole) at early disease onset"],
        "prevention": ["Rotate crops", "Use resistant hybrids", "Bury crop residue"],
        "severity": "high",
    },
    "northern_leaf_blight": {
        "title": "Northern leaf blight",
        "summary": "Fungal disease of maize with long cigar-shaped grey-green lesions.",
        "symptoms": ["Cigar-shaped tan lesions on leaves", "Blighted leaves reduce yield"],
        "treatment": ["Apply fungicide if disease appears before tasseling"],
        "prevention": ["Resistant hybrids", "Crop rotation", "Residue management"],
        "severity": "high",
    },
    "esca": {
        "title": "Esca (Black Measles) - grape",
        "summary": "Complex trunk disease of grapevine.",
        "symptoms": ["Tiger-stripe interveinal scorch on leaves", "Dark spots on berries", "Sudden vine collapse (apoplexy)"],
        "treatment": ["No reliable cure; remove and re-train affected arms", "Protect pruning wounds"],
        "prevention": ["Prune in dry weather & seal large cuts", "Avoid vine stress"],
        "severity": "high",
    },
    "leaf_blight": {
        "title": "Leaf blight (Isariopsis) - grape",
        "summary": "Fungal leaf-spot disease of grape.",
        "symptoms": ["Irregular dark-brown leaf spots", "Premature defoliation"],
        "treatment": ["Apply mancozeb/copper fungicide on a protective schedule"],
        "prevention": ["Canopy management for airflow", "Remove fallen leaves"],
        "severity": "moderate",
    },
    "citrus_greening": {
        "title": "Citrus greening (Huanglongbing/HLB)",
        "summary": "Serious bacterial disease spread by the citrus psyllid. No cure.",
        "symptoms": ["Blotchy asymmetric leaf yellowing", "Lopsided bitter fruit", "Twig dieback"],
        "treatment": ["No cure - remove and destroy infected trees to protect the orchard", "Control psyllid vectors with insecticide"],
        "prevention": ["Use certified disease-free saplings", "Aggressive psyllid control", "Regular scouting"],
        "severity": "critical",
    },
    "bacterial_spot": {
        "title": "Bacterial spot",
        "summary": "Bacterial disease of tomato/pepper/peach causing water-soaked spots.",
        "symptoms": ["Small water-soaked spots turning brown/black", "Yellow halos", "Fruit lesions"],
        "treatment": ["Apply copper-based bactericides (limited efficacy)", "Remove severely infected plants"],
        "prevention": ["Use disease-free certified seed", "Avoid overhead watering & working when wet", "Rotate crops"],
        "severity": "high",
    },
    "early_blight": {
        "title": "Early blight",
        "summary": "Fungal disease (Alternaria) of tomato/potato with target-like spots.",
        "symptoms": ["Brown spots with concentric rings ('target')", "Yellowing around spots", "Lower leaves first"],
        "treatment": ["Apply chlorothalonil or mancozeb fungicide", "Remove infected lower leaves"],
        "prevention": ["Mulch to stop soil splash", "Crop rotation", "Adequate plant spacing"],
        "severity": "moderate",
    },
    "late_blight": {
        "title": "Late blight",
        "summary": "Aggressive disease (Phytophthora infestans) - can destroy a field fast.",
        "symptoms": ["Large grey-green water-soaked patches", "White mold under leaf in humid weather", "Rapid collapse"],
        "treatment": ["Act immediately: apply fungicide (chlorothalonil/mancozeb; metalaxyl)", "Destroy infected plants away from the field"],
        "prevention": ["Plant resistant varieties & certified seed", "Avoid leaf wetness", "Do not compost infected debris"],
        "severity": "critical",
    },
    "leaf_mold": {
        "title": "Leaf mold - tomato",
        "summary": "Fungal disease favoured by high humidity (common in greenhouses/poly-tunnels).",
        "symptoms": ["Pale-yellow spots on upper leaf", "Olive-green/brown velvety mold underneath"],
        "treatment": ["Improve ventilation & lower humidity", "Apply fungicide if severe"],
        "prevention": ["Space plants, prune for airflow", "Avoid wetting foliage"],
        "severity": "moderate",
    },
    "septoria_leaf_spot": {
        "title": "Septoria leaf spot - tomato",
        "summary": "Fungal disease causing many small circular spots.",
        "symptoms": ["Numerous small spots with dark margins & grey centres", "Tiny black specks in centre", "Starts on lower leaves"],
        "treatment": ["Apply fungicide (chlorothalonil/mancozeb)", "Remove infected leaves"],
        "prevention": ["Mulch, rotate crops", "Avoid overhead irrigation"],
        "severity": "moderate",
    },
    "spider_mites": {
        "title": "Two-spotted spider mites",
        "summary": "Tiny sap-sucking pests (not a disease) that stipple and web leaves.",
        "symptoms": ["Fine yellow stippling/speckling", "Fine webbing under leaves", "Bronzing & leaf drop"],
        "treatment": ["Spray water to dislodge; use miticide or insecticidal soap/neem oil", "Encourage predatory mites"],
        "prevention": ["Avoid drought stress & dust", "Avoid broad-spectrum insecticides that kill predators"],
        "severity": "moderate",
    },
    "target_spot": {
        "title": "Target spot - tomato",
        "summary": "Fungal disease (Corynespora) with target-like lesions on leaves and fruit.",
        "symptoms": ["Brown spots with concentric rings", "Lesions on stems & fruit"],
        "treatment": ["Apply fungicide (chlorothalonil/mancozeb)", "Remove infected debris"],
        "prevention": ["Airflow, rotation, avoid leaf wetness"],
        "severity": "moderate",
    },
    "mosaic_virus": {
        "title": "Tomato mosaic virus",
        "summary": "Viral disease causing mottling and distortion. No chemical cure.",
        "symptoms": ["Mottled light/dark green leaves", "Distorted, fern-like leaves", "Stunted plants"],
        "treatment": ["No cure - remove & destroy infected plants", "Disinfect hands/tools (milk or bleach solution)"],
        "prevention": ["Use resistant varieties & clean seed", "Wash hands; avoid tobacco use near plants", "Control weeds"],
        "severity": "high",
    },
    "yellow_leaf_curl_virus": {
        "title": "Tomato yellow leaf curl virus (TYLCV)",
        "summary": "Viral disease spread by whiteflies. No cure.",
        "symptoms": ["Upward curling, yellow leaf margins", "Stunted bushy growth", "Heavy flower drop"],
        "treatment": ["No cure - remove infected plants", "Control whitefly vectors (insecticide, yellow sticky traps)"],
        "prevention": ["Resistant varieties", "Whitefly nets / reflective mulch", "Early whitefly control"],
        "severity": "critical",
    },
}

# Map keywords found in a class name's condition to a KB key.
_CONDITION_RULES = [
    ("healthy", "healthy"),
    ("scab", "apple_scab"),
    ("black_rot", "black_rot"),
    ("rust", "rust"),
    ("powdery", "powdery_mildew"),
    ("cercospora", "gray_leaf_spot"),
    ("gray_leaf", "gray_leaf_spot"),
    ("northern_leaf_blight", "northern_leaf_blight"),
    ("esca", "esca"),
    ("leaf_blight", "leaf_blight"),
    ("haunglongbing", "citrus_greening"),
    ("greening", "citrus_greening"),
    ("bacterial_spot", "bacterial_spot"),
    ("early_blight", "early_blight"),
    ("late_blight", "late_blight"),
    ("leaf_mold", "leaf_mold"),
    ("septoria", "septoria_leaf_spot"),
    ("spider_mites", "spider_mites"),
    ("target_spot", "target_spot"),
    ("mosaic", "mosaic_virus"),
    ("yellow_leaf_curl", "yellow_leaf_curl_virus"),
    ("leaf_scorch", "septoria_leaf_spot"),
]


def _localize_info(info: dict, lang: str = "bn") -> dict:
    """Merge Bengali fields when lang is 'bn'."""
    if lang != "bn":
        return info
    key = info.get("matched_key")
    if not key or key not in DISEASE_INFO_BN:
        return info
    bn = DISEASE_INFO_BN[key]
    out = dict(info)
    for field in ("title", "summary", "symptoms", "treatment", "prevention"):
        if field in bn:
            out[field] = bn[field]
    sev = out.get("severity")
    if sev in SEVERITY_BN:
        out["severity_label"] = SEVERITY_BN[sev]
    return out


def advice_for_key(kb_key: str, lang: str = "bn") -> Optional[dict]:
    if kb_key not in DISEASE_INFO:
        return None
    info = dict(DISEASE_INFO[kb_key])
    info["matched_key"] = kb_key
    return _localize_info(info, lang)


def advice_for(class_name: str, lang: str = "bn") -> Optional[dict]:
    """Return KB info for a full class name like 'Tomato___Late_blight'."""
    cond = class_name.split("___", 1)[1] if "___" in class_name else class_name
    key = cond.lower()
    for needle, kb_key in _CONDITION_RULES:
        if needle in key:
            return advice_for_key(kb_key, lang)
    return None


def all_diseases(lang: str = "bn") -> Dict[str, dict]:
    return {k: advice_for_key(k, lang) for k in DISEASE_INFO}


# --------------------------------------------------------------------------- #
# Rule-based chatbot
# --------------------------------------------------------------------------- #
_BN_EMERGENCY = {
    "16123": ("কৃষি কল সেন্টার (কৃষি হেল্পলাইন)", "সকাল ৯টা - বিকাল ৫টা, শনি-বৃহ"),
    "16358": ("পশুসম্পদ অধিদফতর (পশুচিকিৎসা হেল্পলাইন)", "সকাল ৯টা - বিকাল ৫টা"),
    "999": ("জাতীয় জরুরি সেবা", "২৪/৭"),
}


def _contacts_text(lang: str = "en") -> str:
    if lang == "bn":
        lines = []
        for c in EMERGENCY_CONTACTS:
            bn = _BN_EMERGENCY.get(c["phone"], (c["name"], c["hours"]))
            lines.append(f"- {bn[0]}: {c['phone']} ({bn[1]})")
        return "বাংলাদেশে জরুরি কৃষি/পশুচিকিৎসা হেল্পলাইন:\n" + "\n".join(lines)
    lines = [f"- {c['name']}: {c['phone']} ({c['hours']})" for c in EMERGENCY_CONTACTS]
    return "Here are emergency agriculture/vet hotlines in Bangladesh:\n" + "\n".join(lines)


def _suggestions(lang: str) -> List[str]:
    if lang == "bn":
        return ["অ্যাপ কীভাবে ব্যবহার করব?", "লেট ব্লাইট চিকিৎসা", "পশুচিকিৎসককে কল", "সরকারি লিংক"]
    return ["How do I use this app?", "Treat late blight", "Call a vet", "Government links"]


def chatbot_reply(message: str, context_disease: Optional[str] = None, lang: str = "bn") -> dict:
    """Very small intent-router chatbot. Returns {reply, suggestions}."""
    msg = (message or "").lower().strip()
    bn = lang == "bn"
    suggestions = _suggestions(lang)

    if not msg:
        return {
            "reply": (
                "হাই! আমি এগ্রোভেট সহকারী। পাতার রোগ, চিকিৎসা বা অ্যাপ ব্যবহার সম্পর্কে জিজ্ঞাসা করুন।"
                if bn
                else "Hi! I'm the AgroVet assistant. Ask me about a plant disease, treatment, or how to use the app."
            ),
            "suggestions": suggestions,
        }

    # Greetings
    if re.search(r"\b(hi|hello|hey|salam|assalam|নমস্কার|হ্যালো|আসসালাম)\b", msg):
        return {
            "reply": (
                "হ্যালো! রোগ নির্ণয়ের জন্য পাতার ছবি আপলোড করুন, অথবা রোগ, চিকিৎসা বা জরুরি পশুচিকিৎসা সম্পর্কে জিজ্ঞাসা করুন।"
                if bn
                else "Hello! Upload a leaf photo for diagnosis, or ask me about any disease, treatment, or emergency vet contact."
            ),
            "suggestions": suggestions,
        }

    # Emergency / vet / call
    if re.search(r"\b(emergency|vet|call|hotline|help ?line|doctor|urgent|জরুরি|পশুচিকিৎসক|কল|হেল্পলাইন)\b", msg):
        return {
            "reply": _contacts_text(lang),
            "suggestions": (
                ["লেট ব্লাইট চিকিৎসা", "অ্যাপ কীভাবে ব্যবহার করব?"]
                if bn
                else ["Treat late blight", "How do I use this app?"]
            ),
        }

    # Government links
    if re.search(r"\b(gov|government|link|website|ministry|dae|bari|brri|সরকার|মন্ত্রণালয়|লিংক)\b", msg):
        links = "\n".join(f"- {g['name']}: {g['url']}" for g in GOV_LINKS)
        return {
            "reply": (
                "বাংলাদেশ কৃষির দরকারি সরকারি রিসোর্স:\n" + links
                if bn
                else "Useful Bangladesh agriculture government resources:\n" + links
            ),
            "suggestions": suggestions,
        }

    # How to use
    if re.search(r"\b(how|use|work|start|upload|scan|guide|help|কীভাবে|ব্যবহার|আপলোড|সাহায্য)\b", msg):
        return {
            "reply": (
                "১) একটি পাতার পরিষ্কার ছবি আপলোড বা টেনে আনুন।\n"
                "২) ধাপ ১ এ নিশ্চিত হয় এটি পাতা কিনা।\n"
                "৩) EfficientNet-B3 এআই মডেল দিয়ে পাতার রোগ বিশ্লেষণ করে ফলাফল ও চিকিৎসা পরামর্শ দেখায়।\n"
                "৪) চিকিৎসা পরামর্শ পাবেন; পশুচিকিৎসককে কল বা আমাকে আরও জিজ্ঞাসা করতে পারেন।"
                if bn
                else (
                    "1) Upload or drag a clear photo of a single leaf.\n"
                    "2) Stage 1 checks it really is a leaf.\n"
                    "3) The EfficientNet-B3 AI model analyses the leaf and I show the diagnosis plus treatment advice.\n"
                    "4) You'll get treatment advice, and can call a vet or message me for more help."
                )
            ),
            "suggestions": (
                ["আর্লি ব্লাইট চিকিৎসা", "পশুচিকিৎসককে কল"]
                if bn
                else ["Treat early blight", "Call a vet"]
            ),
        }

    # Treatment / disease lookup - scan KB titles & keys (EN + BN)
    for key, info in DISEASE_INFO.items():
        if key == "healthy":
            continue
        loc = advice_for_key(key, lang)
        title_en = str(info["title"]).lower()
        title_bn = str(DISEASE_INFO_BN.get(key, {}).get("title", "")).lower()
        short_bn = title_bn.split(" - ")[0].strip() if title_bn else ""
        matched = (
            key.replace("_", " ") in msg
            or any(w in msg for w in key.split("_") if len(w) > 3)
            or title_en in msg
            or (title_bn and title_bn in msg)
            or (short_bn and short_bn in msg)
        )
        if not matched:
            continue
        t = "; ".join(loc["treatment"])  # type: ignore
        p = "; ".join(loc["prevention"])  # type: ignore
        sev = loc.get("severity_label") or loc.get("severity")
        if bn:
            return {
                "reply": f"{loc['title']} ({sev} তীব্রতা)\n{loc['summary']}\n\nচিকিৎসা: {t}\nপ্রতিরোধ: {p}",
                "suggestions": ["পশুচিকিৎসককে কল", "সরকারি লিংক", "অ্যাপ কীভাবে ব্যবহার করব?"],
            }
        return {
            "reply": f"{loc['title']} ({sev} severity)\n{loc['summary']}\n\nTreatment: {t}\nPrevention: {p}",
            "suggestions": ["Call a vet", "Government links", "How do I use this app?"],
        }

    # Context-aware fallback
    if context_disease:
        info = advice_for(context_disease, lang)
        if info:
            t = "; ".join(info["treatment"])  # type: ignore
            if bn:
                return {"reply": f"আপনার শেষ ফলাফল ({info['title']}): {t}", "suggestions": suggestions}
            return {"reply": f"For your last result ({info['title']}): {t}", "suggestions": suggestions}

    return {
        "reply": (
            "আমি পাতার রোগ, চিকিৎসা, জরুরি পশুচিকিৎসা ও সরকারি রিসোর্সে সাহায্য করতে পারি। "
            "যেমন জিজ্ঞাসা করুন: 'লেট ব্লাইট চিকিৎসা' বা 'পশুচিকিৎসককে কল'।"
            if bn
            else (
                "I can help with plant-leaf diseases, treatments, emergency vet contacts and government resources. "
                "Try asking e.g. 'how to treat late blight' or 'call a vet'."
            )
        ),
        "suggestions": suggestions,
    }
