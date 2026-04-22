# =========================================================
# IMPORTADOR SEMI-AUTOMÁTICO DE PUBLICACIONES
# =========================================================
# Analiza un link público y trata de extraer:
# - imagen
# - título
# - descripción
# - tienda/usuario
# - precio
#
# Funciona mejor cuando la página trae metadatos Open Graph.
# =========================================================

import re
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}


def get_meta(soup, attr_name, attr_value):
    tag = soup.find("meta", attrs={attr_name: attr_value})
    if tag and tag.get("content"):
        return tag.get("content").strip()
    return ""


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_price(text):
    """
    Intenta detectar precios como:
    $ 1.250.000
    1250000
    ARS 450.000
    """
    if not text:
        return ""

    patterns = [
        r"(?:\$|ARS|ars)\s*([0-9]{1,3}(?:[.\,][0-9]{3})+(?:[\,][0-9]{1,2})?)",
        r"(?:\$|ARS|ars)\s*([0-9]+(?:[\,][0-9]{1,2})?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            value = value.replace(",", ".")
            return value

    return ""


def absolute_image_url(image_url, final_url):
    if not image_url:
        return ""
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url
    if image_url.startswith("//"):
        return "https:" + image_url

    # muy básico
    if final_url.endswith("/") and image_url.startswith("/"):
        return final_url[:-1] + image_url
    elif not final_url.endswith("/") and not image_url.startswith("/"):
        return final_url + "/" + image_url
    else:
        return final_url + image_url


def analyze_publication_link(url, source_type):
    """
    Devuelve un diccionario con datos detectados.
    """
    response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    response.raise_for_status()

    html = response.text
    final_url = response.url

    soup = BeautifulSoup(html, "html.parser")

    og_title = get_meta(soup, "property", "og:title")
    og_description = get_meta(soup, "property", "og:description")
    og_image = get_meta(soup, "property", "og:image")
    og_site_name = get_meta(soup, "property", "og:site_name")

    twitter_title = get_meta(soup, "name", "twitter:title")
    twitter_description = get_meta(soup, "name", "twitter:description")
    twitter_image = get_meta(soup, "name", "twitter:image")

    page_title = clean_text(soup.title.string if soup.title and soup.title.string else "")

    description_tag = get_meta(soup, "name", "description")

    title = og_title or twitter_title or page_title
    description = og_description or twitter_description or description_tag
    image = og_image or twitter_image
    site_name = og_site_name

    # si no encontró imagen en meta, intenta primera img útil
    if not image:
        first_img = soup.find("img")
        if first_img and first_img.get("src"):
            image = first_img.get("src").strip()

    image = absolute_image_url(image, final_url)

    # armamos texto grande para detectar precio
    full_text_candidates = [
        title,
        description,
        page_title,
        description_tag,
        soup.get_text(" ", strip=True)[:5000],
    ]
    full_text = " ".join([clean_text(x) for x in full_text_candidates if x])

    price = detect_price(full_text)

    # tienda o usuario
    tienda = site_name

    if not tienda:
        # si es instagram / facebook intentamos algo simple
        if "instagram.com" in final_url:
            parts = [p for p in final_url.split("/") if p and "instagram.com" not in p and "www." not in p]
            if len(parts) >= 1:
                tienda = parts[1] if len(parts) > 1 else parts[0]
        elif "facebook.com" in final_url:
            parts = [p for p in final_url.split("/") if p and "facebook.com" not in p and "www." not in p]
            if parts:
                tienda = parts[0]

    tienda = clean_text(tienda)

    return {
        "source_type": source_type,
        "source_url": final_url,
        "titulo": clean_text(title),
        "descripcion": clean_text(description),
        "imagen": image,
        "tienda_nombre": tienda,
        "precio": price,
    }