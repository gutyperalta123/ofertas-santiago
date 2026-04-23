# =========================================================
# IMPORTADORES POTENCIADOS
# =========================================================

import json
import re
import html
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


# =========================================================
# UTILIDADES
# =========================================================

def clean_text(text):
    if not text:
        return ""
    text = html.unescape(str(text))
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def shorten_text(text, limit=220):
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def get_meta(soup, attr_name, attr_value):
    tag = soup.find("meta", attrs={attr_name: attr_value})
    if tag and tag.get("content"):
        return clean_text(tag.get("content"))
    return ""


def normalize_link(link, base_url):
    if not link:
        return ""
    return urljoin(base_url, link)


def absolute_image_url(image_url, base_url):
    if not image_url:
        return ""
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url
    if image_url.startswith("//"):
        return "https:" + image_url
    return urljoin(base_url, image_url)


def normalize_price_text(price_text):
    if price_text is None:
        return ""
    price_text = str(price_text).strip()
    if not price_text:
        return ""
    price_text = price_text.replace(",", ".")
    return price_text


def price_to_number_for_sort(price_text):
    if not price_text:
        return float("inf")
    try:
        return float(str(price_text).replace(".", "").replace(",", "."))
    except Exception:
        return float("inf")


def detect_price(text):
    """
    Detecta precios comunes:
    $ 259.999
    ARS 120.000
    1.250.000
    """
    if not text:
        return ""

    text = clean_text(text)

    patterns = [
        r"\$\s*([0-9]{1,3}(?:[.\,][0-9]{3})+)",
        r"\$\s*([0-9]+)",
        r"(?:ARS|ars)\s*([0-9]{1,3}(?:[.\,][0-9]{3})+)",
        r"\b([0-9]{1,3}(?:\.[0-9]{3})+)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            return value.replace(",", ".")

    return ""


def is_bad_title(title):
    title = clean_text(title)
    if not title:
        return True

    lowered = title.lower()

    basura = [
        "sku",
        "iva",
        "sin iva",
        "%",
        "descuento",
        "off",
        "precio",
        "cuotas",
        "código",
        "codigo",
        "ahora",
        "antes",
        "ver más",
        "ver detalle",
        "agregar al carrito",
    ]

    if any(b in lowered for b in basura):
        return True

    # si es solo números, precio o símbolos
    if re.fullmatch(r"[\$0-9\.\,\s\-\%]+", title):
        return True

    if len(title) < 5:
        return True

    return False


def sort_products_by_price(products):
    return sorted(products, key=lambda x: price_to_number_for_sort(x.get("precio", "")))


def dedupe_products(products):
    unique = []
    seen = set()

    for p in products:
        titulo = clean_text(p.get("titulo", ""))
        precio = clean_text(p.get("precio", ""))
        imagen = clean_text(p.get("imagen", ""))
        source_url = clean_text(p.get("source_url", ""))

        if is_bad_title(titulo):
            continue

        # descartamos productos sin precio real
        if not precio or precio in ["0", "0.0", "0.00"]:
            continue

        key = (
            titulo.lower(),
            precio,
            imagen,
            source_url,
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append({
            "titulo": titulo,
            "descripcion": shorten_text(p.get("descripcion", ""), 220),
            "precio": precio,
            "imagen": imagen,
            "source_url": source_url,
            "selected": True,
        })

    return unique


# =========================================================
# IMPORTADOR DE PUBLICACIONES
# =========================================================

def analyze_publication_link(url, source_type):
    response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
    response.raise_for_status()

    final_url = response.url
    soup = BeautifulSoup(response.text, "html.parser")

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
        if first_img:
            img_src = first_img.get("src") or first_img.get("data-src") or ""
            image = absolute_image_url(img_src, final_url)

    full_text = " ".join([
        clean_text(title),
        clean_text(description),
        clean_text(page_title),
        clean_text(description_tag),
        clean_text(soup.get_text(" ", strip=True)[:5000]),
    ])

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

    return {
        "source_type": source_type,
        "source_url": final_url,
        "titulo": clean_text(title),
        "descripcion": shorten_text(description, 220),
        "imagen": absolute_image_url(image, final_url),
        "tienda_nombre": clean_text(tienda),
        "precio": price,
    }


# =========================================================
# REDES DEL SITIO
# =========================================================

def extract_site_social_links(soup, base_url):
    instagram = ""
    facebook = ""
    whatsapp = ""

    for a in soup.find_all("a", href=True):
        href = normalize_link(a.get("href", "").strip(), base_url)
        href_lower = href.lower()

        if not instagram and "instagram.com" in href_lower:
            instagram = href

        if not facebook and "facebook.com" in href_lower:
            facebook = href

        if not whatsapp and (
            "wa.me/" in href_lower
            or "whatsapp.com" in href_lower
            or "api.whatsapp.com" in href_lower
        ):
            whatsapp = href

    return {
        "instagram_link": instagram,
        "facebook_link": facebook,
        "whatsapp_link": whatsapp,
    }


# =========================================================
# JSON-LD / SCHEMA.ORG
# =========================================================

def _walk_jsonld(node, base_url, found_products):
    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, base_url, found_products)
        return

    if not isinstance(node, dict):
        return

    node_type = node.get("@type", "")
    if isinstance(node_type, list):
        node_type = " ".join(node_type)
    node_type = str(node_type).lower()

    if "product" in node_type:
        name = clean_text(node.get("name"))
        description = clean_text(node.get("description"))

        image = node.get("image", "")
        if isinstance(image, list):
            image = image[0] if image else ""
        image = absolute_image_url(str(image), base_url)

        url_value = normalize_link(node.get("url", ""), base_url)

        price = ""
        offers = node.get("offers", {})
        if isinstance(offers, list) and offers:
            offer = offers[0]
            if isinstance(offer, dict):
                price = normalize_price_text(offer.get("price", ""))
        elif isinstance(offers, dict):
            price = normalize_price_text(offers.get("price", ""))

        if name and not is_bad_title(name):
            found_products.append({
                "titulo": name,
                "descripcion": shorten_text(description, 220),
                "precio": price,
                "imagen": image,
                "source_url": url_value,
            })

    if "itemlist" in node_type:
        items = node.get("itemListElement", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    _walk_jsonld(item.get("item", item), base_url, found_products)

    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk_jsonld(value, base_url, found_products)


def extract_jsonld_products(soup, base_url):
    products = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue

        try:
            data = json.loads(raw)
            _walk_jsonld(data, base_url, products)
        except Exception:
            continue

    return products


# =========================================================
# JSON EMBEBIDO
# =========================================================

def safe_json_loads(raw):
    try:
        return json.loads(raw)
    except Exception:
        return None


def deep_extract_products_from_data(data, base_url, found_products):
    if isinstance(data, list):
        for item in data:
            deep_extract_products_from_data(item, base_url, found_products)
        return

    if not isinstance(data, dict):
        return

    possible_title = (
        data.get("name")
        or data.get("title")
        or data.get("productName")
        or data.get("displayName")
    )

    possible_price = (
        data.get("price")
        or data.get("salePrice")
        or data.get("listPrice")
        or data.get("bestPrice")
        or data.get("currentPrice")
        or data.get("formattedPrice")
    )

    possible_image = (
        data.get("image")
        or data.get("imageUrl")
        or data.get("thumbnail")
        or data.get("thumb")
        or data.get("mainImage")
    )

    possible_url = (
        data.get("url")
        or data.get("link")
        or data.get("slug")
        or data.get("productUrl")
    )

    if isinstance(possible_image, list):
        possible_image = possible_image[0] if possible_image else ""

    title = clean_text(possible_title)
    price = normalize_price_text(possible_price)
    image = absolute_image_url(str(possible_image), base_url) if possible_image else ""
    source_url = normalize_link(str(possible_url), base_url) if possible_url else ""
    description = shorten_text(
        data.get("description") or data.get("shortDescription") or "",
        220
    )

    if title and not is_bad_title(title) and price:
        found_products.append({
            "titulo": title,
            "descripcion": description,
            "precio": price,
            "imagen": image,
            "source_url": source_url,
        })

    for value in data.values():
        if isinstance(value, (dict, list)):
            deep_extract_products_from_data(value, base_url, found_products)


def extract_embedded_json_products(soup, base_url):
    products = []

    known_ids = ["__NEXT_DATA__", "__NUXT_DATA__"]

    for sid in known_ids:
        tag = soup.find("script", id=sid)
        if tag:
            raw = tag.string or tag.get_text(strip=True)
            data = safe_json_loads(raw)
            if data is not None:
                deep_extract_products_from_data(data, base_url, products)

    script_texts = soup.find_all("script")
    regexes = [
        r"window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;",
        r"window\.__PRELOADED_STATE__\s*=\s*({.*?})\s*;",
        r"window\.__STATE__\s*=\s*({.*?})\s*;",
    ]

    for script in script_texts:
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue

        for rx in regexes:
            match = re.search(rx, raw, re.DOTALL)
            if match:
                data = safe_json_loads(match.group(1))
                if data is not None:
                    deep_extract_products_from_data(data, base_url, products)

    return products


# =========================================================
# DOM VISUAL
# =========================================================

def extract_dom_products(soup, base_url):
    products = []
    candidate_containers = []

    for tag_name in ["article", "li", "div", "section"]:
        candidate_containers.extend(soup.find_all(tag_name))

    seen = set()

    for tag in candidate_containers:
        text = clean_text(tag.get_text(" ", strip=True))
        if len(text) < 8:
            continue

        a = tag.find("a", href=True)
        img = tag.find("img")

        link = normalize_link(a.get("href"), base_url) if a else ""

        image = ""
        if img:
            image = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
                or ""
            )
            image = absolute_image_url(image, base_url)

        price = detect_price(text)

        title = ""
        for title_tag in tag.find_all(["h1", "h2", "h3", "h4", "strong", "span"]):
            t = clean_text(title_tag.get_text(" ", strip=True))
            if is_bad_title(t):
                continue
            if detect_price(t) and len(t) < 25:
                continue
            if len(t) >= 5:
                title = t
                break

        if not title:
            candidate = text[:120]
            if not is_bad_title(candidate) and not detect_price(candidate):
                title = candidate

        if not title:
            continue

        if not price:
            continue

        if not image and not link:
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


# =========================================================
# IMPORTADOR WEB
# =========================================================

def analyze_web_catalog(url):
    response = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    response.raise_for_status()

    final_url = response.url
    soup = BeautifulSoup(response.text, "html.parser")

    site_name = (
        get_meta(soup, "property", "og:site_name")
        or get_meta(soup, "name", "application-name")
        or clean_text(soup.title.string if soup.title and soup.title.string else "")
    )

    socials = extract_site_social_links(soup, final_url)

    products_jsonld = extract_jsonld_products(soup, final_url)
    products_embedded = extract_embedded_json_products(soup, final_url)
    products_dom = extract_dom_products(soup, final_url)

    all_products = products_jsonld + products_embedded + products_dom
    all_products = dedupe_products(all_products)
    all_products = sort_products_by_price(all_products)

    return {
        "source_url": final_url,
        "tienda_nombre": site_name,
        "instagram_link": socials["instagram_link"],
        "facebook_link": socials["facebook_link"],
        "whatsapp_link": socials["whatsapp_link"],
        "products": all_products[:200],
    }