# =========================================================
# IMPORTADORES SEMI-AUTOMÁTICOS
# =========================================================
# - analyze_publication_link: para publicaciones puntuales
# - analyze_web_catalog: para páginas web / catálogos
# =========================================================

import json
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
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text


def normalize_price_to_text(value):
    if value is None:
        return ""
    value = str(value).strip()
    if not value:
        return ""
    value = value.replace(",", ".")
    return value


def detect_price(text):
    if not text:
        return ""

    patterns = [
        r"(?:\$|ARS|ars)\s*([0-9]{1,3}(?:[.\,][0-9]{3})+(?:[\,][0-9]{1,2})?)",
        r"(?:\$|ARS|ars)\s*([0-9]+(?:[\,][0-9]{1,2})?)",
        r"\b([0-9]{1,3}(?:[.\,][0-9]{3})+)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            value = value.replace(",", ".")
            return value

    return ""


def absolute_image_url(image_url, base_url):
    if not image_url:
        return ""
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url
    if image_url.startswith("//"):
        return "https:" + image_url
    return urljoin(base_url, image_url)


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

        if not whatsapp and (
            "wa.me/" in href_lower
            or "whatsapp.com" in href_lower
            or "api.whatsapp.com" in href_lower
        ):
            whatsapp = href_full

    return {
        "instagram_link": instagram,
        "facebook_link": facebook,
        "whatsapp_link": whatsapp,
    }


def jsonld_to_products(data, base_url):
    products = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return

        if not isinstance(node, dict):
            return

        node_type = node.get("@type", "")
        if isinstance(node_type, list):
            node_type = " ".join(node_type)

        node_type = str(node_type).lower()

        # Product directo
        if "product" in node_type:
            name = clean_text(node.get("name"))
            description = clean_text(node.get("description"))
            image = node.get("image", "")
            if isinstance(image, list):
                image = image[0] if image else ""
            image = absolute_image_url(str(image), base_url)

            offers = node.get("offers", {})
            price = ""

            if isinstance(offers, list) and offers:
                offer = offers[0]
                if isinstance(offer, dict):
                    price = normalize_price_to_text(offer.get("price", ""))
            elif isinstance(offers, dict):
                price = normalize_price_to_text(offers.get("price", ""))

            source_url = normalize_link(node.get("url", ""), base_url)

            if name:
                products.append({
                    "titulo": name,
                    "descripcion": description,
                    "precio": price,
                    "imagen": image,
                    "source_url": source_url,
                })

        # ItemList
        if "itemlist" in node_type:
            items = node.get("itemListElement", [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        walk(item.get("item", item))

        # recorrida general
        for value in node.values():
            if isinstance(value, (dict, list)):
                walk(value)

    walk(data)
    return products


def extract_jsonld_products(soup, base_url):
    products = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue

        try:
            data = json.loads(raw)
            products.extend(jsonld_to_products(data, base_url))
        except Exception:
            # a veces el JSON-LD viene raro; seguimos
            continue

    return products


def extract_dom_products(soup, base_url):
    products = []
    seen = set()

    candidate_containers = []

    for tag_name in ["article", "li", "div", "section"]:
        candidate_containers.extend(soup.find_all(tag_name))

    for tag in candidate_containers:
        text = clean_text(tag.get_text(" ", strip=True))
        if len(text) < 8:
            continue

        a = tag.find("a", href=True)
        img = tag.find("img")

        link = normalize_link(a.get("href"), base_url) if a else ""
        image = ""
        if img:
            image = img.get("src") or img.get("data-src") or img.get("srcset") or ""
            if image and " " in image and "http" in image:
                image = image.split(" ")[0]
            image = absolute_image_url(image, base_url)

        price = detect_price(text)

        title = ""
        for title_tag in tag.find_all(["h1", "h2", "h3", "h4", "strong", "span"]):
            t = clean_text(title_tag.get_text(" ", strip=True))
            if len(t) >= 5 and t.lower() not in ["comprar", "ver más", "agregar al carrito"]:
                title = t
                break

        if not title:
            # tomamos primeras palabras útiles
            title = text[:120]

        # filtro mínimo
        if not title or not image:
            continue

        # para catálogos reales conviene al menos link o precio
        if not link and not price:
            continue

        key = (title.lower(), price, image, link)
        if key in seen:
            continue
        seen.add(key)

        products.append({
            "titulo": clean_text(title),
            "descripcion": "",
            "precio": price,
            "imagen": image,
            "source_url": link,
        })

    return products


def merge_products(products):
    merged = []
    seen = set()

    for p in products:
        titulo = clean_text(p.get("titulo", ""))
        precio = clean_text(p.get("precio", ""))
        imagen = clean_text(p.get("imagen", ""))
        link = clean_text(p.get("source_url", ""))

        if len(titulo) < 4:
            continue

        key = (
            titulo.lower(),
            precio,
            imagen,
            link
        )

        if key in seen:
            continue

        seen.add(key)
        merged.append({
            "titulo": titulo,
            "descripcion": clean_text(p.get("descripcion", "")),
            "precio": precio,
            "imagen": imagen,
            "source_url": link,
            "selected": True,
        })

    return merged


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

    jsonld_products = extract_jsonld_products(soup, final_url)
    dom_products = extract_dom_products(soup, final_url)

    products = merge_products(jsonld_products + dom_products)

    return {
        "source_url": final_url,
        "tienda_nombre": site_name,
        "instagram_link": socials["instagram_link"],
        "facebook_link": socials["facebook_link"],
        "whatsapp_link": socials["whatsapp_link"],
        "products": products[:150],
    }