# =========================================================
# IMPORTADORES SEMI-AUTOMÁTICOS
# =========================================================
# - analyze_publication_link: para publicaciones puntuales
# - analyze_web_catalog: para páginas web / catálogos
# =========================================================

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


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
    return urljoin(final_url, image_url)


def normalize_link(link, base_url):
    if not link:
        return ""
    return urljoin(base_url, link)


def analyze_publication_link(url, source_type):
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

    if not image:
        first_img = soup.find("img")
        if first_img and first_img.get("src"):
            image = first_img.get("src").strip()

    image = absolute_image_url(image, final_url)

    full_text_candidates = [
        title,
        description,
        page_title,
        description_tag,
        soup.get_text(" ", strip=True)[:5000],
    ]
    full_text = " ".join([clean_text(x) for x in full_text_candidates if x])

    price = detect_price(full_text)

    tienda = site_name

    if not tienda:
        if "instagram.com" in final_url:
            parts = [p for p in final_url.split("/") if p and "instagram.com" not in p and "www." not in p]
            if parts:
                tienda = parts[0]
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


def extract_site_social_links(soup, base_url):
    instagram = ""
    facebook = ""
    whatsapp = ""

    links = soup.find_all("a", href=True)

    for a in links:
        href = a.get("href", "").strip()
        href_full = normalize_link(href, base_url)

        href_lower = href_full.lower()

        if not instagram and "instagram.com" in href_lower:
            instagram = href_full

        if not facebook and "facebook.com" in href_lower:
            facebook = href_full

        if not whatsapp and ("wa.me/" in href_lower or "whatsapp.com" in href_lower or "api.whatsapp.com" in href_lower):
            whatsapp = href_full

    return {
        "instagram_link": instagram,
        "facebook_link": facebook,
        "whatsapp_link": whatsapp,
    }


def looks_like_product_card(text, link, image):
    text = clean_text(text)
    if len(text) < 8:
        return False
    if not link:
        return False
    if not image:
        return False
    return True


def extract_candidate_cards(soup, base_url):
    candidates = []

    selectors = [
        ["article"],
        ["div", "li", "section"],
    ]

    seen = set()

    # intento 1: artículos
    for tag_name in selectors[0]:
        for tag in soup.find_all(tag_name):
            text = clean_text(tag.get_text(" ", strip=True))
            a = tag.find("a", href=True)
            img = tag.find("img", src=True)

            link = normalize_link(a.get("href"), base_url) if a else ""
            image = absolute_image_url(img.get("src"), base_url) if img else ""
            price = detect_price(text)

            # buscar título
            title = ""
            for title_tag in tag.find_all(["h1", "h2", "h3", "h4", "strong", "span"]):
                t = clean_text(title_tag.get_text(" ", strip=True))
                if len(t) >= 5:
                    title = t
                    break

            if not title:
                title = text[:120]

            if looks_like_product_card(title or text, link, image):
                key = (title, price, image, link)
                if key not in seen:
                    seen.add(key)
                    candidates.append({
                        "titulo": clean_text(title),
                        "descripcion": "",
                        "precio": price,
                        "imagen": image,
                        "source_url": link,
                    })

    # intento 2: div/li/section con clase sugerente
    keywords = ["product", "item", "card", "post", "listing", "box"]

    for tag_name in selectors[1]:
        for tag in soup.find_all(tag_name):
            classes = " ".join(tag.get("class", [])).lower()
            if not any(k in classes for k in keywords):
                continue

            text = clean_text(tag.get_text(" ", strip=True))
            a = tag.find("a", href=True)
            img = tag.find("img", src=True)

            link = normalize_link(a.get("href"), base_url) if a else ""
            image = absolute_image_url(img.get("src"), base_url) if img else ""
            price = detect_price(text)

            title = ""
            for title_tag in tag.find_all(["h1", "h2", "h3", "h4", "strong", "span"]):
                t = clean_text(title_tag.get_text(" ", strip=True))
                if len(t) >= 5:
                    title = t
                    break

            if not title:
                title = text[:120]

            if looks_like_product_card(title or text, link, image):
                key = (title, price, image, link)
                if key not in seen:
                    seen.add(key)
                    candidates.append({
                        "titulo": clean_text(title),
                        "descripcion": "",
                        "precio": price,
                        "imagen": image,
                        "source_url": link,
                    })

    return candidates


def analyze_web_catalog(url):
    response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
    response.raise_for_status()

    html = response.text
    final_url = response.url

    soup = BeautifulSoup(html, "html.parser")

    site_name = (
        get_meta(soup, "property", "og:site_name")
        or clean_text(soup.title.string if soup.title and soup.title.string else "")
    )

    socials = extract_site_social_links(soup, final_url)
    products = extract_candidate_cards(soup, final_url)

    # limpiamos títulos muy repetidos o feos
    cleaned_products = []
    seen_titles_links = set()

    for p in products:
        titulo = clean_text(p.get("titulo", ""))
        if len(titulo) < 4:
            continue

        key = (titulo.lower(), p.get("source_url", ""))
        if key in seen_titles_links:
            continue
        seen_titles_links.add(key)

        cleaned_products.append({
            "titulo": titulo,
            "descripcion": p.get("descripcion", ""),
            "precio": p.get("precio", ""),
            "imagen": p.get("imagen", ""),
            "source_url": p.get("source_url", ""),
            "selected": True,
        })

    return {
        "source_url": final_url,
        "tienda_nombre": site_name,
        "instagram_link": socials["instagram_link"],
        "facebook_link": socials["facebook_link"],
        "whatsapp_link": socials["whatsapp_link"],
        "products": cleaned_products[:100],  # límite razonable
    }