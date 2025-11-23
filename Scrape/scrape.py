from bs4 import BeautifulSoup
import csv
import re
from typing import List, Dict
import os
import argparse


def parse_listings_from_html(html: str) -> List[Dict[str, str]]:
    """Parse the provided HTML and return a list of listing dicts.

    Each dict has keys: 'pièces', 'chambres', 'surface (m²)', 'étage'.
    Values are strings or None.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Each apartment listing is usually in a <div> with 'data-testid' containing 'classified-card'
    listings = soup.find_all("div", {"data-testid": lambda v: v and "classified-card" in v})

    results: List[Dict[str, str]] = []
    seen_texts = set()

    for listing in listings:
        text = listing.get_text(" ", strip=True)
        # Normalize whitespace for deduplication key
        norm_text = re.sub(r"\s+", " ", text).strip()
        if norm_text in seen_texts:
            # skip duplicate listing blocks
            continue
        seen_texts.add(norm_text)

        pieces = None
        chambres = None
        surface = None
        etage = None
        prix = None

        pieces_match = re.search(r"(\d+)\s*pièces?", text)
        chambres_match = re.search(r"(\d+)\s*chambres?", text)
        surface_match = re.search(r"(\d+[,\.]?\d*)\s*m²", text)

        # price: prefer dedicated price element (many cards use data-testid that contains 'price')
        price_el = listing.find(attrs={"data-testid": lambda v: v and "price" in v})
        price_text = None
        if price_el:
            # get visible text from the price element
            price_text = price_el.get_text(" ", strip=True)
        # fallback to any euro amount in the listing text
        if price_text:
            price_match = re.search(r"(\d{1,3}(?:[ \u00A0\u202F]\d{3})*(?:[.,]\d+)?)\s*€", price_text)
        else:
            price_match = re.search(r"(\d{1,3}(?:[ \u00A0\u202F]\d{3})*(?:[.,]\d+)?)\s*€", text)

        # assign parsed values for pieces/chambres/surface
        if pieces_match:
            pieces = pieces_match.group(1)
        if chambres_match:
            chambres = chambres_match.group(1)
        if surface_match:
            surface = surface_match.group(1)

        # Improved étage detection: handle forms like
        # - '3ème étage'
        # - '1er étage'
        # - 'Étage 3/1' or 'Etage 3/1'
        # - 'RDC' or 'rez-de-chaussée'
        # We'll try a few ordered patterns so we don't accidentally pick up numbers from surface/rooms.
        # 1) Explicit 'RDC' or 'rez-de-chaussée'
        rdcm = re.search(r"(?i)\b(RDC|rez[- ]de[- ]chauss(?:e|ée))\b", text)
        if rdcm:
            etage = rdcm.group(1)
        else:
            # 2) Number immediately before 'étage' e.g. '3ème étage' or '1er étage'
            m = re.search(r"(?i)(\d+(?:er|ème|e|ère)?(?:/\d+)?)\s*(?:ème|er|e|ère)?\s*é?t?age\b", text)
            if m:
                etage = m.group(1)
            else:
                # 3) 'étage' followed by a number (e.g. 'Étage 3/1')
                m2 = re.search(r"(?i)é?t?age\s*(\d+(?:/\d+)?)", text)
                if m2:
                    etage = m2.group(1)

        # Normalize common variants for clarity
        if etage:
            etage = etage.strip()
            # Uppercase RDC and normalize 'rez-de-chaussée' to 'RDC'
            if re.search(r"(?i)^(?:rdc|rez[- ]de[- ]chauss)", etage):
                etage = "RDC"
            else:
                # If we only captured digits like '3', append 'ème' for readability
                if re.fullmatch(r"\d+", etage):
                    etage = etage + "ème"
                # Keep ordinal suffixes (er, ème, etc.) and '3/1' forms as-is

        # Convert étage to numeric string for CSV: RDC->0, ordinals -> digits, '3/5' -> 3
        etage_val = ""
        if etage:
            # If explicit RDC
            if re.search(r"(?i)^RDC$", etage):
                etage_val = "0"
            else:
                # If form like '3/5' or '3/3', take the left-hand number
                slash_m = re.match(r"^(\d+)\s*/\s*\d+$", etage)
                if slash_m:
                    etage_val = slash_m.group(1)
                else:
                    # Extract first digits from variants like '3ème', '1er', '2e', or plain '3'
                    digit_m = re.search(r"(\d+)", etage)
                    if digit_m:
                        etage_val = digit_m.group(1)
        # leave etage_val as empty string if nothing matched

        # Normalize price (remove spaces/non-breaking spaces, convert comma decimals to dot)
        if price_match:
            raw = price_match.group(1)
            # remove common space separators: normal space, no-break space, narrow no-break
            norm = raw.replace('\u00A0', '').replace('\u202F', '').replace(' ', '').replace(',', '.')
            prix = norm

        results.append({
            "pièces": pieces,
            "chambres": chambres,
            "surface (m²)": surface,
            "étage": etage_val,
            "prix (€)": prix,
        })

    return results


def scrape_from_file(html_path: str = "page.html") -> List[Dict[str, str]]:
    """Read an HTML file and return parsed listing dicts."""
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    return parse_listings_from_html(html)


def detect_ville_from_html(html: str) -> str:
    """Try to detect the city (ville) from the provided HTML.

    Heuristics (in order):
    - Find occurrences like 'Antibes (06600)' and pick the most frequent city name found.
    - Fall back to searching the <title> or visible text for a probable city name.
    Returns a slug-like lowercased string (spaces -> '-') or an empty string if detection fails.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    # 1) City with postal code in parentheses: 'Ville (06000)'
    matches = re.findall(r"([A-ZÀ-Ÿ][A-Za-zÀ-ÿ'\- ,]+?)\s*\((\d{5})\)", text)
    if matches:
        # pick most common city name
        cities = [m[0].strip() for m in matches]
        from collections import Counter
        most_common = Counter(cities).most_common(1)[0][0]
        return _slugify_city(most_common)

    # 2) Try title tag (may contain city)
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        # look for words that look like city names (capitalized words)
        m = re.search(r"([A-ZÀ-Ÿ][A-Za-zÀ-ÿ'\- ]{2,})", title)
        if m:
            return _slugify_city(m.group(1))

    # 3) As a last resort try to find a standalone postal code and take nearby words
    m2 = re.search(r"(\d{5})", text)
    if m2:
        idx = m2.start()
        # take a window before the postal code and try to find capitalized chunk
        window = text[max(0, idx - 200): idx + 10]
        m3 = re.search(r"([A-ZÀ-Ÿ][A-Za-zÀ-ÿ'\- ]{2,})\s*\d{5}", window)
        if m3:
            return _slugify_city(m3.group(1))

    return ""


def _slugify_city(name: str) -> str:
    """Normalize a city name to a simple slug: lowercase, spaces -> '-', remove punctuation."""
    s = name.strip()
    # remove parentheses and commas
    s = re.sub(r"[(),]", " ", s)
    # remove other non-word chars except spaces and hyphens
    s = re.sub(r"[^\w\s\-àâäéèêëîïôöùûüÿçÀÂÄÉÈÊËÎÏÔÖÙÛÜŸÇ-]", "", s, flags=re.U)
    s = s.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s


def load_locations_file(path: str) -> List[str]:
    """Load locations from a text file, one per line. Returns list of names (raw)."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            if ln.startswith("#"):
                continue
            out.append(ln)
    return out


def detect_ville_using_locations(html: str, locations: List[str]) -> str:
    """Try to find the best matching location from the provided locations list inside the HTML text.

    Returns slugified city name or empty string.
    """
    if not locations:
        return ""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    counts = []
    for loc in locations:
        # count simple occurrences of the location name (case-insensitive)
        pattern = re.escape(loc)
        c = len(re.findall(pattern, text, flags=re.IGNORECASE))
        if c > 0:
            counts.append((c, loc))
    if not counts:
        return ""
    counts.sort(reverse=True)
    best = counts[0][1]
    return _slugify_city(best)


def write_results_to_csv(results: List[Dict[str, str]], out_path: str, ville: str, append_if_exists: bool = True) -> None:
    """Write the list of result dicts to a CSV file with UTF-8 encoding.

    If the output CSV already exists and append_if_exists is True, append rows and do not
    rewrite the header; otherwise create/overwrite the file and write a header.

    Adds a 'ville' column with the provided city name.
    """
    # Field order including ville and prix
    fieldnames = ["pièces", "chambres", "surface (m²)", "étage", "prix (€)", "ville"]

    write_header = True
    mode = "w"
    if append_if_exists and os.path.exists(out_path):
        # Append mode, but only if file exists
        mode = "a"
        write_header = False

    # Ensure directory exists when given a path with folders
    with open(out_path, mode, newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in results:
            # Normalize None -> empty string for CSV and add ville
            safe_row = {k: (v if v is not None else "") for k, v in row.items()}
            safe_row["ville"] = ville
            # Ensure all fieldnames present (in case older results miss some keys)
            out_row = {fn: safe_row.get(fn, "") for fn in fieldnames}
            writer.writerow(out_row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape page.html and export listings to CSV with a ville column.")
    parser.add_argument("--ville", "-v", help="City name to include in each row (auto-detected from HTML if omitted)")
    parser.add_argument("--output", "-o", help="Output CSV filename (will prompt if not provided)")
    parser.add_argument("--html", "-i", default="page.html", help="Input HTML file to scrape (default: page.html)")
    parser.add_argument("--locations-file", "-l", default="locations.txt", help="Path to locations.txt containing candidate villes (one per line).")
    parser.add_argument("--no-append", action="store_true", help="Overwrite output file instead of appending if it exists")
    args = parser.parse_args()

    # Ask for ville if not provided via CLI
    # Read HTML first so we can auto-detect the ville when omitted
    html_path = args.html
    if not os.path.exists(html_path):
        print(f"Input HTML file not found: {html_path}")
        raise SystemExit(1)
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    ville = args.ville
    if not ville:
        # try locations file first
        locs = load_locations_file(args.locations_file)
        if locs:
            ville = detect_ville_using_locations(html_content, locs)
            if ville:
                print(f"Detected ville from locations file: {ville}")
        # fallback to general detection
        if not ville:
            ville = detect_ville_from_html(html_content)
            if ville:
                print(f"Detected ville: {ville}")
            else:
                # fallback to prompting if detection failed
                ville = input("Ville (city) name to add to rows (detection failed): ").strip()
    # final fallback to empty string
    if not ville:
        ville = ""

    # Get filename from CLI or prompt
    filename = args.output
    if not filename:
        filename = input("Output CSV filename (e.g. listings.csv) [default: listings.csv]: ").strip()
    if not filename:
        filename = "listings.csv"
    if not filename.lower().endswith(".csv"):
        filename = filename + ".csv"

    # Use already-read HTML to avoid re-reading
    results = parse_listings_from_html(html_content)
    append_flag = not args.no_append
    write_results_to_csv(results, filename, ville, append_if_exists=append_flag)
    print(f"Wrote {len(results)} rows to {filename} (ville='{ville}')")
