import csv
import json
import requests
import time
from typing import Optional

# Configuration - adjust paths and cookies as needed
BASE_URL = "http://79.137.38.40:8069/web/dataset/call_kw"
HEADERS = {
    "Content-Type": "application/json",
    # Keep the same cookie used for authentication in the UI
    "Cookie": "tz=Africa/Tunis; session_id=5e5854353cb49ac19ad0c48d99c0927dbd3fd6e4; cids=1"
}

# Defaults - update input path to your ventes CSV
INPUT_FILE = "Test_data/input_vente.csv"
OUTPUT_FILE = "Predictions/output_prediction_vente.csv"


def make_context(view_id: int = 6) -> dict:
    # Model used in the UI traces: 'prediction.request'
    return {
        "lang": "en_US",
        "tz": "Africa/Tunis",
        "uid": 2,
        "allowed_company_ids": [1],
        "params": {
            "cids": 1,
            "menu_id": 75,
            "action": 89,
            "model": "prediction.request",
            "view_type": "form",
            "id": view_id,
        },
    }


def make_web_save_payload(req_id: int, city: str, pieces: int, bedrooms: int,
                          surface: float, floor: int, type_val: str = "app",
                          state: str = "draft", view_id: int = 6) -> dict:
    values = {
        "state": state,
        "city": city,
        "type": "_",
        "pieces": pieces,
        "bedrooms": bedrooms,
        "surface": surface,
        "location": "_",
        "floor": floor,
        "description": False,
    }
    return {
        "id": req_id,
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "prediction.request",
            "method": "web_save",
            "args": [[], values],
            "kwargs": {
                "context": make_context(view_id),
                "specification": {
                    "state": {}, "city": {}, "type": {}, "pieces": {}, "bedrooms": {},
                    "surface": {}, "location": {}, "floor": {}, "description": {},
                    "prediction": {}, "error_message": {}, "display_name": {}
                }
            }
        }
    }


def make_action_get_prediction_payload(req_id: int, record_id: int, view_id: int = 6) -> dict:
    return {
        "id": req_id,
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "prediction.request",
            "method": "action_get_prediction",
            "args": [[record_id]],
            "kwargs": {"context": make_context(view_id)},
        },
    }


def make_web_read_payload(req_id: int, record_id: int, view_id: int = 6) -> dict:
    return {
        "id": req_id,
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "prediction.request",
            "method": "web_read",
            "args": [[record_id]],
            "kwargs": {
                "context": dict(list(make_context(view_id).items()) + [("bin_size", True)]),
                "specification": {
                    "state": {}, "city": {}, "type": {}, "pieces": {}, "bedrooms": {},
                    "surface": {}, "location": {}, "floor": {}, "description": {},
                    "prediction": {}, "error_message": {}, "display_name": {}
                }
            }
        }
    }


def send_json(payload: dict, timeout: int = 15) -> dict:
    # Build a best-effort endpoint using the model and method from payload
    try:
        model = payload.get("params", {}).get("model", "prediction.request")
        method = payload.get("params", {}).get("method", "web_read")
        url = f"{BASE_URL}/{model}/{method}"
    except Exception:
        url = BASE_URL
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def extract_created_id_from_web_save_response(resp_json) -> Optional[int]:
    if resp_json is None:
        return None
    if isinstance(resp_json, dict) and "result" in resp_json:
        r = resp_json["result"]
        if isinstance(r, list) and r:
            first = r[0]
            if isinstance(first, dict) and "id" in first:
                return int(first["id"])
            if isinstance(first, int):
                return int(first)
        if isinstance(r, int):
            return int(r)

    def find_int(d):
        if isinstance(d, int):
            return d
        if isinstance(d, dict):
            for v in d.values():
                res = find_int(v)
                if res is not None:
                    return res
        if isinstance(d, list):
            for item in d:
                res = find_int(item)
                if res is not None:
                    return res
        return None

    cand = find_int(resp_json)
    return int(cand) if cand is not None else None


def normalize_row(row: dict):
    """Normalize and fill missing values according to rules:
    - if surface missing -> return None (drop row)
    - if 'chambres' missing -> bedrooms = max(0, pieces - 1)
    - if 'pièces' missing -> pieces = bedrooms + 1
    - if 'étage' missing -> 0
    Returns a dict with numeric keys: 'pièces','chambres','surface','étage','ville'
    """
    # surface is mandatory
    surf_raw = row.get("surface (m²)") or row.get("surface") or ""
    surf_raw = str(surf_raw).strip()
    if not surf_raw:
        return None
    try:
        surface = float(surf_raw.replace(",", "."))
    except Exception:
        return None

    # pièces and chambres parsing
    pieces_raw = row.get("pièces") or row.get("pieces") or ""
    chambres_raw = row.get("chambres") or row.get("chambre") or ""

    pieces = None
    chambres = None
    try:
        if str(pieces_raw).strip():
            pieces = int(str(pieces_raw).strip())
    except Exception:
        pieces = None
    try:
        if str(chambres_raw).strip():
            chambres = int(str(chambres_raw).strip())
    except Exception:
        chambres = None

    # Apply derivation rules
    if chambres is None and pieces is not None:
        # bedrooms = pieces - 1 (min 0)
        chambres = max(0, pieces - 1)
    if pieces is None and chambres is not None:
        pieces = chambres + 1
    # If both missing, default to zeros
    if pieces is None and chambres is None:
        pieces = 0
        chambres = 0

    # étage default to 0
    floor_raw = row.get("étage") or row.get("etage") or ""
    try:
        étage = int(str(floor_raw).strip()) if str(floor_raw).strip() else 0
    except Exception:
        étage = 0

    ville = (row.get("ville") or "").strip()

    return {
        "pièces": int(pieces),
        "chambres": int(chambres),
        "surface": float(surface),
        "étage": int(étage),
        "ville": ville,
    }


def get_prediction_for_row(row: dict, req_id_counter_start: int = 1, view_id: int = 6,
                           debug: bool = False, probe_delay: float = 0.12):
    """Perform web_save -> action_get_prediction -> web_read sequence and return (prediction, last_req_id_used)"""
    # normalize the row values using the same rules as main loop
    normalized = normalize_row(row)
    if normalized is None:
        return None, req_id_counter_start

    req_id = req_id_counter_start
    city = normalized.get("ville", "")
    pieces = normalized.get("pièces", 0)
    bedrooms = normalized.get("chambres", 0)
    surface = normalized.get("surface", 0.0)
    floor = normalized.get("étage", 0)

    # 1) web_save
    payload_save = make_web_save_payload(req_id, city, pieces, bedrooms, surface, floor, view_id=view_id)
    if debug:
        print("web_save payload:", json.dumps(payload_save)[:1000])
    resp_save = send_json(payload_save)
    if debug:
        print("web_save resp:", resp_save)
    created_id = extract_created_id_from_web_save_response(resp_save)
    if created_id is None:
        return None, req_id
    req_id += 1
    time.sleep(probe_delay)

    # 2) action_get_prediction
    payload_action = make_action_get_prediction_payload(req_id, created_id, view_id=view_id)
    if debug:
        print("action payload:", json.dumps(payload_action)[:1000])
    resp_action = send_json(payload_action)
    if debug:
        print("action resp:", resp_action)
    req_id += 1
    time.sleep(probe_delay)

    # 3) web_read
    payload_read = make_web_read_payload(req_id, created_id, view_id=view_id)
    if debug:
        print("read payload:", json.dumps(payload_read)[:1000])
    resp_read = send_json(payload_read)
    if debug:
        print("read resp:", resp_read)

    pred = None
    try:
        if isinstance(resp_read, dict) and "result" in resp_read:
            r = resp_read["result"]
            if isinstance(r, list) and r:
                first = r[0]
                if isinstance(first, dict) and "prediction" in first:
                    pred = first.get("prediction")
    except Exception:
        pred = None

    return pred, req_id


if __name__ == "__main__":
    # Main loop reads CSV and writes predictions
    with open(INPUT_FILE, newline='', encoding='utf-8') as infile, \
         open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as outfile:

        reader = csv.DictReader(infile)
        fieldnames = (reader.fieldnames or []) + ['prix_predicté']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for i, row in enumerate(reader, start=1):
            try:
                # Normalize inputs and apply fill rules
                normalized = normalize_row(row)
                if normalized is None:
                    # surface missing or invalid -> skip (do not write)
                    print(f"⏭️ Skipping line {i}: missing or invalid surface")
                    continue

                # update the row for output consistency
                row["surface (m²)"] = str(normalized["surface"]).replace('.', ',')
                row["pièces"] = str(normalized["pièces"])
                row["chambres"] = str(normalized["chambres"])
                row["étage"] = str(normalized["étage"])
                city = normalized.get("ville", "")

                pred, last_req = get_prediction_for_row(row, req_id_counter_start=(i*3), view_id=6, debug=False)

                if pred is not None:
                    print(f"✅ {city} → {pred}")
                    row["prix_predicté"] = pred
                else:
                    print(f"⚠️ {city} → No prediction for line {i}")
                    row["prix_predicté"] = "Erreur"

            except Exception as e:
                print(f"❌ Error on line {i}: {e}")
                row["prix_predicté"] = "Erreur"

            writer.writerow(row)

    print(f"\n✅ Finished! Results saved in {OUTPUT_FILE}")
