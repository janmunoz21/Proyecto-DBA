import os
import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from pymongo import MongoClient, GEOSPHERE
from pymongo import UpdateOne
from datetime import datetime, timezone

CHUNK_SIZE = 5_000

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "upme-project"


def ensure_spatial_indexes(db, col_name: str):

    # Crea un índice geoespacial 2dsphere de manera preventiva 
    # esto asegura que las consultas geoespaciales sean eficientes
    print(f"-> Asegurando índice geoespacial 2dsphere en la coleccion '{col_name}'...")
    db[col_name].create_index([("geometry", GEOSPHERE)])
    print(f" Indexación exitosa en '{col_name}'\n")


def _parse_ms_partition(fp: str) -> pd.DataFrame:
    """
    Lee una partición Microsoft. El formato real es GeoJSONL comprimido
    (un objeto JSON por línea) aunque la extensión sea .csv.gz.
    Si la primera línea parece CSV (contiene una cabecera de texto), usa
    el parser CSV con on_bad_lines='skip' como fallback.
    """
    import gzip

    rows = []
    with gzip.open(fp, "rt", encoding="utf-8") as fh:
        first_line = fh.readline().strip()
        # GeoJSONL: la primera línea es un objeto JSON
        if first_line.startswith("{"):
            try:
                rows.append(json.loads(first_line))
            except json.JSONDecodeError:
                pass
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            return pd.DataFrame(rows)
        else:
            # Fallback CSV: cabecera en primera línea
            import io
            fh.seek(0) if hasattr(fh, "seek") else None

    # Re-abrir para el fallback CSV (gzip no soporta seek)
    with gzip.open(fp, "rt", encoding="utf-8") as fh:
        return pd.read_csv(fh, on_bad_lines="skip")


def _read_microsoft_partitions(folder: str) -> gpd.GeoDataFrame:
    """
    Lee todos los archivos .csv.gz de una carpeta de particiones Microsoft
    y devuelve un GeoDataFrame con CRS EPSG:4326.
    """
    files = sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith(".csv.gz")
    ])
    if not files:
        raise FileNotFoundError(f"No se encontraron archivos .csv.gz en '{folder}'")

    print(f"  Leyendo {len(files)} particiones de Microsoft...")
    frames = []
    for i, fp in enumerate(files, 1):
        df = _parse_ms_partition(fp)
        frames.append(df)
        print(f"  [{i}/{len(files)}] {os.path.basename(fp)} — {len(df):,} filas", end="\r")

    print()
    combined = pd.concat(frames, ignore_index=True)

    # La geometría puede estar en columna 'geometry' (GeoJSON) o venir del propio objeto JSON
    if "geometry" in combined.columns:
        def _to_shape(val):
            if isinstance(val, str):
                return shape(json.loads(val))
            if isinstance(val, dict):
                return shape(val)
            return None

        geometries = combined["geometry"].apply(_to_shape)
    else:
        raise ValueError("No se encontró columna 'geometry' en las particiones de Microsoft.")

    gdf = gpd.GeoDataFrame(combined, geometry=geometries, crs="EPSG:4326")
    return gdf


def _read_google_file(file_path: str) -> gpd.GeoDataFrame:
    """
    Lee un archivo de Google Open Buildings (.csv.gz o .csv).
    Columnas esperadas: latitude, longitude, geometry (WKT), confidence, area_in_meters, full_plus_code.
    """
    from shapely import wkt as shapely_wkt

    print(f"  Leyendo archivo Google: {file_path}")
    df = pd.read_csv(file_path, compression="gzip" if file_path.endswith(".gz") else None)

    if "geometry" in df.columns:
        geometries = df["geometry"].apply(shapely_wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry=geometries, crs="EPSG:4326")
    else:
        raise ValueError("El archivo Google no contiene columna 'geometry'.")

    return gdf


def _flush_chunk(collection, documents: list) -> int:
    """Envía un chunk a MongoDB con upsert y retorna cuántos fueron nuevos."""
    ops = [
        UpdateOne(
            {"geometry": doc["geometry"], "dataset_source": doc["dataset_source"]},
            {"$setOnInsert": doc},
            upsert=True,
        )
        for doc in documents
    ]
    result = collection.bulk_write(ops, ordered=False)
    return result.upserted_count


def run_buildings_ingestion(file_path: str, dataset_type: str):
    """
    Lee huellas de edificios (Microsoft o Google), calcula área en m²
    y aplica upsert por chunks en MongoDB.
    """
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col_name = f"buildings_{dataset_type}"
    collection = db[col_name]

    ensure_spatial_indexes(db, col_name)

    # ── Lectura según formato del dataset ──────────────────────
    print(f"\nCargando datos de {dataset_type.upper()}...")
    if dataset_type == "microsoft":
        gdf = _read_microsoft_partitions(file_path)
    else:
        gdf = _read_google_file(file_path)

    print(f"  {len(gdf):,} registros cargados.")

    # ── CRS → WGS84 para MongoDB ───────────────────────────────
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        print("  Reproyectando a WGS84 (EPSG:4326)...")
        gdf = gdf.to_crs(epsg=4326)

    # ── Área en m² (EPSG:9377, sistema métrico oficial Colombia) ─
    print("  Calculando áreas en EPSG:9377 (Magnus)...")
    gdf["area_m2"] = gdf.to_crs(epsg=9377).geometry.area

    # ── Ingesta por chunks ─────────────────────────────────────
    total    = len(gdf)
    inserted = 0
    chunk    = []
    now      = datetime.now(timezone.utc)
    num_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE

    print(f"  Escribiendo {total:,} registros en {num_chunks} chunks (upsert)...")

    for idx, (_, row) in enumerate(gdf.iterrows(), 1):
        geom = row["geometry"]
        if geom is None or geom.is_empty:
            continue

        doc = {
            "geometry":       geom.__geo_interface__,
            "area_m2":        round(float(row["area_m2"]), 2),
            "dataset_source": dataset_type,
            "ingested_at":    now,
        }

        if dataset_type == "google":
            if "confidence" in row and pd.notna(row["confidence"]):
                doc["confidence_score"] = float(row["confidence"])

        chunk.append(doc)

        if len(chunk) >= CHUNK_SIZE:
            inserted += _flush_chunk(collection, chunk)
            chunk_n = (idx // CHUNK_SIZE)
            pct = idx / total * 100
            print(f"  Chunk {chunk_n}/{num_chunks}  ({idx:,}/{total:,} — {pct:.1f}%)  "
                  f"nuevos acumulados: {inserted:,}")
            chunk = []

    if chunk:
        inserted += _flush_chunk(collection, chunk)

    print(f"\n  Ingesta completada: {inserted:,} nuevos documentos insertados.\n")
    client.close()