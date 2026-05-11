import pandas as pd
import geopandas as gpd
from pymongo import MongoClient, GEOSPHERE
from datetime import datetime, timezone

MONGO_URI  = "mongodb://localhost:27017/"
DB_NAME    = "upme-project"
COL_NAME   = "municipalities"
SHP_PATH   = "MGN_2025_COLOMBIA/ADMINISTRATIVO/MGN_ADM_MPIO_GRAFICO.shp"
PDET_XLSX  = "MunicipiosPDET.xlsx"

def load_pdet_codes(xlsx_path: str) -> set:
    """Carga los códigos DANE de municipios PDET desde el Excel oficial."""
    df = pd.read_excel(xlsx_path)
    # Columna: 'Código DANE Municipio' — viene como int (ej. 19050), zfill a 5 dígitos
    codes = set(df["Código DANE Municipio"].astype(str).str.zfill(5))
    print(f"  Municipios PDET en Excel: {len(codes)}")
    return codes

def run_ingestion(shapefile_path: str):
    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COL_NAME]

    # 1. Cargar códigos PDET desde Excel
    print("Cargando lista PDET desde Excel...")
    pdet_codes = load_pdet_codes(PDET_XLSX)

    # 2. Leer shapefile
    print("\nLeyendo shapefile...")
    gdf = gpd.read_file(shapefile_path)
    print(f"  Total municipios MGN : {len(gdf)}")
    print(f"  CRS original         : {gdf.crs}")

    # 3. Calcular área en m² en CRS métrico oficial de Colombia
    print("Calculando áreas en EPSG:9377 (Magnus)...")
    gdf["area_m2"] = gdf.to_crs(epsg=9377).geometry.area

    # 4. Reproyectar a WGS84 para MongoDB 2dsphere
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # 5. Construir código DIVIPOLA 5 dígitos y filtrar PDET
    gdf["dane_code"] = (
        gdf["dpto_ccdgo"].astype(str).str.zfill(2) +
        gdf["mpio_ccdgo"].astype(str).str.zfill(3)
    )
    gdf_pdet = gdf[gdf["dane_code"].isin(pdet_codes)].copy()
    print(f"  Municipios PDET encontrados en shapefile: {len(gdf_pdet)}")

    # 6. Construir documentos
    records = []
    for _, row in gdf_pdet.iterrows():
        geom = row["geometry"].__geo_interface__
        if geom["type"] == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
        records.append({
            "dane_code":   row["dane_code"],
            "name":        row["mpio_cnmbr"],
            "department":  row["dpto_cnmbr"],
            "is_pdet":     True,
            "geometry":    geom,
            "area_m2":     round(float(row["area_m2"]), 2),
            "source":      "MGN2025",
            "ingested_at": datetime.now(timezone.utc),
        })

    # 7. Upsert en MongoDB
    print(f"\nCargando {len(records)} documentos en MongoDB...")
    for doc in records:
        col.update_one({"dane_code": doc["dane_code"]}, {"$set": doc}, upsert=True)
    print(f" {len(records)} municipios sincronizados")

    # 8. Índice 2dsphere
    col.create_index([("geometry", GEOSPHERE)])
    print(" Índice 2dsphere creado")

    # 9. Verificación
    print(f"\nVerificación")
    print(f"  Documentos en colección : {col.count_documents({})}")
    print(f"  Índices                 : {[i['name'] for i in col.list_indexes()]}")
    muestra = col.find_one({}, {"_id": 0, "dane_code": 1, "name": 1, "area_m2": 1})
    print(f"  Muestra                 : {muestra}")

    client.close()
    print("\nIngesta completada.")

#if __name__ == "__main__":
#    run_ingestion(SHP_PATH)
