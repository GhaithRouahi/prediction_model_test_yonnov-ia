import csv
import json
import requests
import time

URL = "http://79.137.38.40:8069/web/dataset/call_kw/prediction.rent.request/predict_rent"
HEADERS = {
    "Content-Type": "application/json",
    "Cookie": "tz=Africa/Tunis; session_id=5e5854353cb49ac19ad0c48d99c0927dbd3fd6e4; cids=1"
}


INPUT_FILE = "../location/input.csv"
OUTPUT_FILE = "Predictions/output.csv"


def make_context(view_id=6):
    return {
        "lang": "en_US",
        "tz": "Africa/Tunis",
        "uid": 2,
        "allowed_company_ids": [1],
        "params": {
            "cids": 1,
            "menu_id": 72,
            "action": 88,
            "model": "prediction.rent.request",
            "view_type": "form",
            "id": view_id
        }
    }

def make_web_save_payload(req_id: int, city: str, pieces:int, bedrooms:int,
                          surface:float, floor:int, type_val:str="app",
                          state:str="draft", view_id:int=6):
    values = {
        "state": state,
        "city": city,
        "type": type_val,
        "pieces": pieces,
        "bedrooms": bedrooms,
        "surface": surface,
        "location": False,
        "floor": floor,
        "description": False
    }
    return {
        "id": req_id,
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "prediction.rent.request",
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

def make_action_get_prediction_payload(req_id: int, record_id: int, view_id:int=6):
    return {
        "id": req_id,
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "prediction.rent.request",
            "method": "action_get_prediction",
            "args": [[record_id]],
            "kwargs": {
                "context": make_context(view_id)
            }
        }
    }

def make_web_read_payload(req_id: int, record_id: int, view_id:int=6):
    return {
        "id": req_id,
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "prediction.rent.request",
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

def send_json(payload, timeout=15):
    resp = requests.post(URL, headers=HEADERS, json=payload, timeout=timeout)
    resp.raise_for_status()
    # return parsed json or raise JSON decode error
    return resp.json()

def extract_created_id_from_web_save_response(resp_json):
    # Try several likely shapes:
    # 1) resp['result'] is a list with dict containing 'id'
    # 2) resp['result'] is an int (the created id)
    # 3) resp itself might be {'result': <int>} or [{'id': <int>}, ...]
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
    # fallback: search nested for first integer id-looking value (less safe)
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

def get_prediction_for_row(row, req_id_counter_start=1, view_id=6, debug=False, probe_delay=0.1):
    """Perform web_save -> action_get_prediction -> web_read sequence and return (prediction, last_req_id_used)"""
    req_id = req_id_counter_start
    city = row.get("ville","")
    try:
        pieces = int(row.get("pièces") or 0)
    except: pieces = 0
    try:
        bedrooms = int(row.get("chambres") or 0)
    except: bedrooms = 0
    try:
        surface = float(str(row.get("surface (m²)") or "0").replace(",", "."))
    except: surface = 0.0
    try:
        floor = int(row.get("étage") or 0)
    except: floor = 0

    # 1) web_save
    payload_save = make_web_save_payload(req_id, city, pieces, bedrooms, surface, floor, view_id=view_id)
    if debug: print("web_save payload:", json.dumps(payload_save)[:1000])
    resp_save = send_json(payload_save)
    if debug: print("web_save resp:", resp_save)
    created_id = extract_created_id_from_web_save_response(resp_save)
    if created_id is None:
        return None, req_id  # failed to create
    req_id += 1
    time.sleep(probe_delay)

    # 2) action_get_prediction
    payload_action = make_action_get_prediction_payload(req_id, created_id, view_id=view_id)
    if debug: print("action payload:", json.dumps(payload_action)[:1000])
    resp_action = send_json(payload_action)
    if debug: print("action resp:", resp_action)
    req_id += 1
    time.sleep(probe_delay)

    # 3) web_read (to read record including prediction)
    payload_read = make_web_read_payload(req_id, created_id, view_id=view_id)
    if debug: print("read payload:", json.dumps(payload_read)[:1000])
    resp_read = send_json(payload_read)
    if debug: print("read resp:", resp_read)

    # Parse prediction from resp_read: common pattern: resp_read['result'][0]['prediction']
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

# read CSV file
with open(INPUT_FILE, newline='', encoding='utf-8') as infile, \
     open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as outfile:
    
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames + ['prix_predicté']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()

    for i, row in enumerate(reader, start=1):
        try:
            # Clean and convert values
            surface_str = row["surface (m²)"].replace(",", ".").strip()
            surface = float(surface_str)
            floor = int(row["étage"]) if row["étage"].strip() else 0
            pieces = int(row["pièces"]) if row["pièces"].strip() else 0
            bedrooms = int(row["chambres"]) if row["chambres"].strip() else 0
            city = row["ville"].strip()

            # 1) web_save
            payload_save = make_web_save_payload(i, city, pieces, bedrooms, surface, floor)
            response_save = send_json(payload_save)

            created_id = extract_created_id_from_web_save_response(response_save)
            if created_id is None:
                print(f"❌ Failed to create record for {city} (line {i})")
                row["prix_predicté"] = "Erreur"
                writer.writerow(row)
                continue

            # 2) action_get_prediction
            payload_action = make_action_get_prediction_payload(i + 1, created_id)
            response_action = send_json(payload_action)

            # 3) web_read (to read record including prediction)
            payload_read = make_web_read_payload(i + 2, created_id)
            response_read = send_json(payload_read)

            # Parse prediction from response_read
            prediction = None
            try:
                if isinstance(response_read, dict) and "result" in response_read:
                    r = response_read["result"]
                    if isinstance(r, list) and r:
                        first = r[0]
                        if isinstance(first, dict) and "prediction" in first:
                            prediction = first.get("prediction")
            except Exception:
                prediction = None

            if prediction is not None:
                print(f"✅ {city} → {prediction}")
                row["prix_predicté"] = prediction
            else:
                print(f"⚠️ {city} → No prediction found in response JSON")
                row["prix_predicté"] = "Erreur"

        except Exception as e:
            print(f"❌ Error on line {i}: {e}")
            row["prix_predicté"] = "Erreur"

        writer.writerow(row)

print(f"\n✅ Finished! Results saved in {OUTPUT_FILE}")
