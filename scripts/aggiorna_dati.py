import os
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

FILE_STAZIONI = "data/stazioni.csv"
FILE_PORTATE = "data/portate.csv"

BASE_HIS = "http://hiscentral.isprambiente.gov.it/hiscentral/webservices/hiscentral.asmx"

# Bounding box del Friuli-Venezia Giulia (Tagliamento, Isonzo, Livenza, Stella)
BBOX_FVG = {
    "xmin": 12.30,
    "xmax": 13.90,
    "ymin": 45.60,
    "ymax": 46.65
}

def scopri_serie_fvg():
    """Interroga il catalogo ISPRA HIS Central nell'area del FVG per trovare stazioni e variabili reali."""
    url = f"{BASE_HIS}/GetSeriesCatalogForBox2"
    params = {
        "xmin": BBOX_FVG["xmin"],
        "xmax": BBOX_FVG["xmax"],
        "ymin": BBOX_FVG["ymin"],
        "ymax": BBOX_FVG["ymax"],
        "conceptKeyword": "",
        "networkIDs": "",
        "beginDate": "2020-01-01",
        "endDate": datetime.now(timezone.utc).strftime("%Y-%m-%d")
    }
    resp = requests.get(url, params=params, timeout=45)
    resp.raise_for_status()
    
    root = ET.fromstring(resp.content)
    catalogo = []
    
    for series in root.iter():
        if series.tag.endswith("SeriesRecord"):
            rec = {}
            for child in series:
                tag_name = child.tag.split("}")[-1]
                rec[tag_name] = child.text.strip() if child.text else ""
            
            var_name = rec.get("VarName", "").lower()
            # Filtra per portate (discharge/portata) o livelli idrometrici (level/livello/altezza)
            if any(k in var_name for k in ["portat", "discharg", "livell", "idrometr", "stage", "height"]):
                catalogo.append({
                    "id_stazione": rec.get("SiteCode", "").replace(":", "_"),
                    "codice_ispra": rec.get("SiteCode", ""),
                    "variabile_ispra": rec.get("VarCode", ""),
                    "nome_variabile": rec.get("VarName", ""),
                    "nome": rec.get("SiteName", "Stazione FVG"),
                    "fiume": rec.get("SiteName", "").split("-")[0].strip(),
                    "lat": float(rec.get("Latitude", 0)),
                    "lon": float(rec.get("Longitude", 0)),
                    "bacino": "Alpi Orientali (FVG)",
                    "serv_url": rec.get("ServURL", "")
                })
    return pd.DataFrame(catalogo)

def scarica_valori_wml(serv_url, site_code, var_code, start_date, end_date):
    """Scarica i valori dal servizio WaterOneFlow specifico della rete."""
    # Costruisce l'endpoint REST GetValuesObject dal WSDL/ServURL della rete
    base_url = serv_url.split("?")[0]
    if not base_url.endswith("GetValuesObject"):
        base_url = base_url.rstrip("/") + "/GetValuesObject"
        
    params = {
        "location": site_code,
        "variable": var_code,
        "startDate": start_date,
        "endDate": end_date,
        "authToken": ""
    }
    resp = requests.get(base_url, params=params, timeout=30)
    resp.raise_for_status()
    
    root = ET.fromstring(resp.content)
    valori = []
    for elem in root.iter():
        if elem.tag.endswith("value") and elem.text is not None:
            dt = elem.attrib.get("dateTime", "")[:10]
            try:
                val = float(elem.text.strip())
                if val > -9000 and dt:
                    valori.append((dt, val))
            except ValueError:
                continue
    return valori

def aggiorna():
    print("Ricerca stazioni idrometriche reali in FVG su ISPRA HIS Central...")
    try:
        df_cat = scopri_serie_fvg()
    except Exception as e:
        print(f"Errore interrogazione catalogo ISPRA: {e}")
        return

    print(f"Serie idrometriche trovate nel catalogo FVG: {len(df_cat)}")
    if df_cat.empty:
        return

    # Mantieni una serie per stazione (preferendo la portata se disponibile, altrimenti il livello)
    df_cat["is_portata"] = df_cat["nome_variabile"].str.lower().str.contains("portat|discharg")
    df_cat = df_cat.sort_values(by=["is_portata"], ascending=False).drop_duplicates(subset=["id_stazione"])
    
    # Limita alle prime 15 stazioni principali per mantenere veloce l'esecuzione
    df_cat = df_cat.head(15)

    # Salva l'anagrafica reale in data/stazioni.csv
    cols_staz = ["id_stazione", "codice_ispra", "variabile_ispra", "nome", "fiume", "lat", "lon", "bacino"]
    df_cat[cols_staz].to_csv(FILE_STAZIONI, index=False)
    print(f"Salvata anagrafica con {len(df_cat)} stazioni reali in {FILE_STAZIONI}.")

    # Carica eventuale storico esistente
    if os.path.exists(FILE_PORTATE):
        df_storico = pd.read_csv(FILE_PORTATE)
        df_storico = df_storico[df_storico["id_stazione"].isin(df_cat["id_stazione"])]
    else:
        df_storico = pd.DataFrame(columns=["id_stazione", "data", "portata_m3s"])

    # Scarica gli ultimi 30 giorni di dati reali
    oggi = datetime.now(timezone.utc).date()
    start_str = (oggi - timedelta(days=30)).strftime("%Y-%m-%d")
    end_str = oggi.strftime("%Y-%m-%d")

    righe_nuove = []
    for _, row in df_cat.iterrows():
        try:
            serie = scarica_valori_wml(
                row["serv_url"],
                row["codice_ispra"],
                row["variabile_ispra"],
                start_str,
                end_str
            )
            for dt, val in serie:
                righe_nuove.append({
                    "id_stazione": row["id_stazione"],
                    "data": dt,
                    "portata_m3s": round(val, 2)
                })
            print(f"[{row['nome']}] Scaricati {len(serie)} valori.")
        except Exception as e:
            print(f"[{row['nome']}] Nessun dato recente ({e})")

    df_nuovi = pd.DataFrame(righe_nuove, columns=["id_stazione", "data", "portata_m3s"])
    df_finale = pd.concat([df_storico, df_nuovi], ignore_index=True)

    if not df_finale.empty:
        df_finale["data"] = pd.to_datetime(df_finale["data"]).dt.strftime("%Y-%m-%d")
        # Media giornaliera nel caso la stazione trasmetta dati orari/sub-orari
        df_finale = df_finale.groupby(["id_stazione", "data"], as_index=False)["portata_m3s"].mean()
        df_finale["portata_m3s"] = df_finale["portata_m3s"].round(2)
        df_finale = df_finale.sort_values(by=["data", "id_stazione"])

    df_finale.to_csv(FILE_PORTATE, index=False)
    print(f"Database aggiornato: {len(df_finale)} righe totali in {FILE_PORTATE}.")

if __name__ == "__main__":
    aggiorna()
