import json
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "AIBirdLab/1.0 (educational local bird identification)"
TIMEOUT = 12

IUCN_STATUS = {
    "Q211005": "найменший ризик (LC)",
    "Q719675": "близький до загрозливого (NT)",
    "Q278113": "вразливий (VU)",
    "Q11394": "під загрозою (EN)",
    "Q219127": "на межі зникнення (CR)",
    "Q237350": "зниклий у природі (EW)",
    "Q239509": "зниклий (EX)",
    "Q3245245": "недостатньо даних (DD)",
}


def lookup_bird(scientific_name: str):
    empty = {"description": "", "details": "", "common_name": ""}
    name = " ".join(scientific_name.split())
    if not name or "_" in name:
        return empty

    try:
        summary = get_json(
            "https://en.wikipedia.org/api/rest_v1/page/summary/"
            + urllib.parse.quote(name.replace(" ", "_"))
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        return empty

    if summary.get("type") == "disambiguation":
        return empty

    description = ""
    page_url = page_url_(summary)
    uk_title = ""
    try:
        uk_title = ukrainian_title(summary.get("titles", {}).get("canonical", ""))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        uk_title = ""
    if uk_title:
        try:
            uk_summary = get_json(
                "https://uk.wikipedia.org/api/rest_v1/page/summary/"
                + urllib.parse.quote(uk_title.replace(" ", "_"))
            )
            description = shorten(uk_summary.get("extract") or "")
            page_url = page_url_(uk_summary) or page_url
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
            description = ""
    if not description:
        description = shorten(summary.get("extract") or "")

    common_name = ""
    iucn = ""
    qid = summary.get("wikibase_item")
    if qid:
        try:
            common_name, iucn = wikidata_facts(qid)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
            common_name, iucn = "", ""

    details = details_(common_name, iucn, page_url)
    return {
        "description": description,
        "details": details,
        "common_name": common_name,
    }


def details_(common_name: str, iucn: str, page_url: str) -> str:
    lines = []
    if common_name:
        lines.append(f"Звичайна назва (Вікідані): {common_name}")
    if iucn:
        lines.append(f"Статус МСОП (Вікідані): {iucn}")
    if page_url:
        lines.append(f"Сторінка: {page_url}")
    if lines:
        lines.append("Джерела: Вікіпедія, Вікідані")
    return "\n".join(lines)


def wikidata_facts(qid: str) -> tuple[str, str]:
    payload = get_json(
        "https://www.wikidata.org/w/api.php?"
        + urllib.parse.urlencode({
            "action": "wbgetentities",
            "ids": qid,
            "props": "labels|claims",
            "languages": "uk|en",
            "format": "json",
        })
    )
    entity = payload["entities"][qid]
    labels = entity.get("labels") or {}
    claims = entity.get("claims") or {}
    common_name = ""
    uk_label = (labels.get("uk") or {}).get("value")
    en_label = (labels.get("en") or {}).get("value")
    if uk_label:
        common_name = uk_label
    else:
        common_name = common_name_(claims, "uk") or en_label or common_name_(claims, "en") or ""

    iucn = ""
    status = claim_value(claims, "P141")
    if isinstance(status, dict):
        iucn = IUCN_STATUS.get(status.get("id") or "", "")
    return common_name, iucn


def common_name_(claims: dict, language: str) -> str:
    for claim in claims.get("P1843") or []:
        value = snak_value(claim)
        if isinstance(value, dict) and value.get("language") == language and value.get("text"):
            return value["text"]
    return ""


def claim_value(claims: dict, pid: str):
    group = claims.get(pid) or []
    preferred = [claim for claim in group if claim.get("rank") == "preferred"]
    for claim in preferred or group:
        if (claim.get("mainsnak") or {}).get("snaktype") == "value":
            return snak_value(claim)
    return None


def snak_value(claim: dict):
    return ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")


def ukrainian_title(canonical_title: str) -> str:
    if not canonical_title:
        return ""
    payload = get_json(
        "https://en.wikipedia.org/w/api.php?"
        + urllib.parse.urlencode({
            "action": "query",
            "titles": canonical_title,
            "redirects": 1,
            "prop": "langlinks",
            "lllang": "uk",
            "format": "json",
        })
    )
    pages = (payload.get("query") or {}).get("pages") or {}
    for page in pages.values():
        for link in page.get("langlinks") or []:
            title = link.get("title") or link.get("*") or ""
            if title:
                return title
    return ""


def page_url_(summary: dict) -> str:
    return (
        ((summary.get("content_urls") or {}).get("desktop") or {}).get("page")
        or ""
    )


def shorten(text: str, limit: int = 420) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    cut = compact[:limit]
    dot = cut.rfind(". ")
    if dot >= 80:
        return cut[:dot + 1]
    return cut.rstrip() + "…"


def get_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)