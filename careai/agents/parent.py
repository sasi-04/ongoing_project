"""Parent Communication Agent: plain-language, empathetic summary."""
from .. import llm


def summarise(case, plan, kb):
    lines = []
    for k in ("accommodations", "strategies", "services"):
        for r in plan[k]:
            itv = kb.interventions.get(r["intervention_id"])
            lines.append(itv["parent_text"] if itv else r["text"])
    goals = [g["statement"].replace("curriculum-based assessment ", "") for g in plan["goals"]]
    body = ("Thank you for being part of your child's team. This is a DRAFT that the school team will review with you "
            "before anything is final.\n\nWhat we plan to do:\n" + "\n".join(f"- {l}" for l in lines) +
            ("\n\nWhat we hope to see in about 12 weeks:\n" + "\n".join(f"- {g}" for g in goals) if goals else "") +
            "\n\nYou know your child best. Please tell us what fits, what doesn't, and what we may be missing.")
    lang = case.demographics.primary_language or "en"
    out, source = body, "template"
    if lang != "en" and llm.available():
        t = llm.generate(f"Translate to language code '{lang}', keep a warm tone, keep bullet points:\n{body}")
        if t:
            out, source = t, f"llm-translation:{lang}"
    return {"language": lang if source != "template" else "en", "text": out, "source": source,
            "note": "" if lang == "en" or source != "template" else f"Translation to '{lang}' needs the local LLM; shown in English."}
