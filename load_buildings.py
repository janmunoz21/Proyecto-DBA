import os
import json
import gzip
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import shape, mapping, MultiPolygon, Polygon, GeometryCollection, box
from shapely.geometry.polygon import orient
from shapely.validation import make_valid
from shapely import STRtree
from pymongo import MongoClient, GEOSPHERE, UpdateOne, DeleteOne, WriteConcern
from pymongo.errors import BulkWriteError, ServerSelectionTimeoutError, OperationFailure
from datetime import datetime, timezone
from pyproj import Geod

CHUNK_SIZE = 10_000
MS_STREAM_CHUNK = 15_000
GOOGLE_STREAM_CHUNK = 15_000

_GEOD = Geod(ellps="WGS84")

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "upme-project"


# ═══════════════════════════════════════════════════════════════
# Geometry sanitization
# ═══════════════════════════════════════════════════════════════

def _sanitize_geometry(geom, return_shapely=False):
    """
    Valida, repara y normaliza una geometría para MongoDB 2dsphere.
    Retorna dict GeoJSON MultiPolygon o None si irrecuperable.
    Si return_shapely=True, retorna (dict, shapely_geom) para evitar reconversión.
    """
    if geom is None or geom.is_empty:
        return (None, None) if return_shapely else None

    if not geom.is_valid:
        geom = make_valid(geom)

    if geom is None or geom.is_empty:
        return (None, None) if return_shapely else None

    polygons = []
    if isinstance(geom, Polygon):
        polygons = [geom]
    elif isinstance(geom, MultiPolygon):
        polygons = list(geom.geoms)
    elif isinstance(geom, GeometryCollection):
        for part in geom.geoms:
            if isinstance(part, Polygon) and not part.is_empty:
                polygons.append(part)
            elif isinstance(part, MultiPolygon):
                polygons.extend(g for g in part.geoms if not g.is_empty)
    else:
        return (None, None) if return_shapely else None

    if not polygons:
        return (None, None) if return_shapely else None

    oriented = [orient(p, sign=1.0) for p in polygons]
    multi = MultiPolygon(oriented)

    if multi.is_empty:
        return (None, None) if return_shapely else None

    geo = mapping(multi)
    geo["type"] = "MultiPolygon"

    if return_shapely:
        return geo, multi
    return geo


# ═══════════════════════════════════════════════════════════════
# PDET spatial filter (STRtree-based, much faster than union)
# ═══════════════════════════════════════════════════════════════

def _load_pdet_filter():
    """
    Carga municipios PDET y construye un filtro espacial optimizado:
    - bbox: para descartar particiones enteras y prefiltro por coordenadas
    - strtree: para intersects eficiente sin necesidad de unary_union
    Retorna (bbox, strtree, geoms_list)

    Usa STRtree en vez de unary_union para evitar memory issues
    con la union de 170 poligonos complejos.
    """
    _check_mongo_connection(MONGO_URI)
    client = MongoClient(MONGO_URI)
    cursor = client[DB_NAME]["municipalities"].find(
        {"is_pdet": True}, {"geometry": 1, "_id": 0}
    ).batch_size(20)
    docs = list(cursor)
    client.close()

    if not docs:
        raise RuntimeError(
            "No se encontraron municipios PDET en MongoDB. "
            "Ejecuta primero la opcion 1 (Cargar datos)."
        )

    geoms = [shape(d["geometry"]).simplify(0.001, preserve_topology=True) for d in docs]
    print(f"  Filtro PDET: {len(geoms)} municipios cargados")

    pdet_bbox = box(*gpd.GeoSeries(geoms).total_bounds)
    tree = STRtree(geoms)

    print(f"  PDET bbox: {pdet_bbox.bounds}")
    return pdet_bbox, tree, geoms


# ═══════════════════════════════════════════════════════════════
# Microsoft partition streaming (fixes MemoryError)
# ═══════════════════════════════════════════════════════════════

def _iter_ms_partition(fp: str, chunksize: int = MS_STREAM_CHUNK, pdet_bounds=None):
    """
    Lee una partición Microsoft en streaming por chunks.
    Aplica prefiltro por bounding box a nivel de coordenadas crudas
    ANTES de crear objetos Shapely (ahorro masivo de memoria).
    """
    if pdet_bounds is not None:
        pdet_minx, pdet_miny, pdet_maxx, pdet_maxy = pdet_bounds

    rows = []
    with gzip.open(fp, "rt", encoding="utf-8") as fh:
        first_line = fh.readline().strip()

        if first_line.startswith("{"):
            lines_iter = _chain_first_line(first_line, fh)
            for line in lines_iter:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                geom_raw = obj.get("geometry")
                if isinstance(geom_raw, str):
                    try:
                        geom_raw = json.loads(geom_raw)
                    except json.JSONDecodeError:
                        continue
                if not geom_raw:
                    continue

                # Prefiltro por bbox usando coordenadas crudas (sin crear Shapely)
                if pdet_bounds is not None:
                    if not _geojson_intersects_bbox(geom_raw, pdet_minx, pdet_miny, pdet_maxx, pdet_maxy):
                        continue

                rows.append(geom_raw)

                if len(rows) >= chunksize:
                    yield _geojson_list_to_gdf(rows)
                    rows = []

            if rows:
                yield _geojson_list_to_gdf(rows)
        else:
            pass

    if not first_line.startswith("{"):
        with gzip.open(fp, "rt", encoding="utf-8") as fh:
            reader = pd.read_csv(fh, on_bad_lines="skip", chunksize=chunksize)
            for df_chunk in reader:
                if "geometry" not in df_chunk.columns:
                    continue
                geoms = []
                for v in df_chunk["geometry"].values:
                    if isinstance(v, str) and v.startswith("{"):
                        try:
                            geoms.append(shape(json.loads(v)))
                        except Exception:
                            geoms.append(None)
                    else:
                        geoms.append(None)
                gdf = gpd.GeoDataFrame(df_chunk, geometry=geoms, crs="EPSG:4326")
                yield gdf


def _chain_first_line(first_line, fh):
    """Itera first_line + resto del filehandle."""
    yield first_line
    yield from fh


def _geojson_intersects_bbox(geom_dict: dict, minx, miny, maxx, maxy) -> bool:
    """
    Verifica rápidamente si un GeoJSON dict intersecta un bbox,
    usando solo las coordenadas (sin crear Shapely). Muy rápido.
    """
    coords = geom_dict.get("coordinates")
    if not coords:
        return False

    gtype = geom_dict.get("type", "")
    try:
        if gtype == "Polygon":
            ring = coords[0]
        elif gtype == "MultiPolygon":
            ring = coords[0][0]
        else:
            return True  # tipos desconocidos: pasar al filtro preciso

        # Verificar si algún punto del primer anillo cae en el bbox
        for lon, lat in ring:
            if minx <= lon <= maxx and miny <= lat <= maxy:
                return True
        return False
    except (IndexError, TypeError):
        return True  # en caso de duda, no descartar


def _geojson_list_to_gdf(geojson_list: list) -> gpd.GeoDataFrame:
    """Convierte lista de GeoJSON dicts a GeoDataFrame."""
    geoms = [shape(g) for g in geojson_list]
    return gpd.GeoDataFrame({"geometry": geoms}, geometry="geometry", crs="EPSG:4326")


def _partition_intersects_pdet(fp: str, pdet_bbox) -> bool:
    """
    Lee las primeras ~100 geometrías de una partición para determinar
    su extent espacial. Si el extent no intersecta el bbox PDET,
    la partición entera se puede saltar.
    """
    sample_geoms = []
    try:
        with gzip.open(fp, "rt", encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i >= 50:
                    break
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    obj = json.loads(line)
                    geom = obj.get("geometry")
                    if isinstance(geom, str):
                        geom = json.loads(geom)
                    if geom:
                        sample_geoms.append(shape(geom))
                except Exception:
                    continue
    except Exception:
        return True  # en caso de duda, procesar

    if not sample_geoms:
        return True

    # Calcular el extent de la muestra y expandir 0.5 grados como margen
    gs = gpd.GeoSeries(sample_geoms)
    minx, miny, maxx, maxy = gs.total_bounds
    margin = 0.5
    partition_bbox = box(minx - margin, miny - margin, maxx + margin, maxy + margin)
    return partition_bbox.intersects(pdet_bbox)


# ═══════════════════════════════════════════════════════════════
# Google tile streaming
# ═══════════════════════════════════════════════════════════════

def _iter_google_tile(fp: str, chunksize: int = GOOGLE_STREAM_CHUNK, pdet_bounds=None):
    """
    Itera sobre un tile de Google en chunks desde archivo local.
    Aplica prefiltro por lat/lon ANTES de parsear WKT (ahorro masivo de CPU/RAM).
    """
    from shapely import from_wkt

    usecols = lambda c: c in ("geometry", "confidence", "area_in_meters", "latitude", "longitude")
    with gzip.open(fp, "rt", encoding="utf-8") as gz:
        reader = pd.read_csv(gz, chunksize=chunksize, usecols=usecols)
        for df_chunk in reader:
            if "geometry" not in df_chunk.columns:
                raise ValueError(f"El tile Google no contiene columna 'geometry': {fp}")

            # Prefiltro por lat/lon antes de crear objetos Shapely
            if pdet_bounds is not None and "latitude" in df_chunk.columns:
                minx, miny, maxx, maxy = pdet_bounds
                mask = (
                    (df_chunk["longitude"] >= minx) & (df_chunk["longitude"] <= maxx) &
                    (df_chunk["latitude"]  >= miny) & (df_chunk["latitude"]  <= maxy)
                )
                df_chunk = df_chunk[mask]
                if df_chunk.empty:
                    continue

            geometries = from_wkt(df_chunk["geometry"].values)
            df_chunk = df_chunk.drop(columns=["geometry", "latitude", "longitude"], errors="ignore")
            gdf = gpd.GeoDataFrame(df_chunk, geometry=geometries, crs="EPSG:4326")
            valid_mask = ~gdf.geometry.isna()
            if valid_mask.any():
                yield gdf[valid_mask].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════
# Progress tracking
# ═══════════════════════════════════════════════════════════════

def _progress_file(dataset_type: str) -> str:
    return f"{dataset_type}_buildings_progress.json"


def _load_progress(dataset_type: str) -> set:
    fp = _progress_file(dataset_type)
    if os.path.isfile(fp):
        with open(fp) as f:
            return set(json.load(f))
    return set()


def _save_progress(dataset_type: str, done: set):
    with open(_progress_file(dataset_type), "w") as f:
        json.dump(list(done), f)


# ═══════════════════════════════════════════════════════════════
# Core ingestion (optimized with prepared geometry + bbox prefilter)
# ═══════════════════════════════════════════════════════════════

def _flush_chunk(collection, documents: list) -> int:
    """Inserta un chunk en MongoDB. Retorna cantidad insertada."""
    if not documents:
        return 0
    try:
        collection.insert_many(documents, ordered=False)
        return len(documents)
    except BulkWriteError as bwe:
        return bwe.details.get("nInserted", 0)


def _ingest_gdf(gdf: gpd.GeoDataFrame, collection, dataset_type: str,
                now: datetime, pdet_tree=None, pdet_bbox=None) -> int:
    """
    Sanitiza geometrías, filtra por PDET, calcula áreas e ingesta.
    Usa STRtree para intersects eficiente y Geod para área geodésica
    (sin reproyección). Para Google usa area_in_meters de la fuente.
    """
    if len(gdf) == 0:
        return 0

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Filtro espacial con STRtree
    if pdet_tree is not None:
        geom_array = gdf["geometry"].values
        hit_indices = pdet_tree.query(geom_array, predicate="intersects")
        if len(hit_indices[0]) == 0:
            return 0
        unique_building_indices = np.unique(hit_indices[0])
        gdf = gdf.iloc[unique_building_indices].reset_index(drop=True)
        if len(gdf) == 0:
            return 0

    # Google provee area_in_meters directamente
    has_source_area = (dataset_type == "google" and "area_in_meters" in gdf.columns)
    has_conf = (dataset_type == "google" and "confidence" in gdf.columns)

    # Sanitizar geometrías — return_shapely=True para calcular área sin reconversión
    need_geod_area = not has_source_area
    sanitized_geojsons = []
    sanitized_shapely = []
    valid_indices = []

    for i, geom in enumerate(gdf["geometry"].values):
        if need_geod_area:
            result = _sanitize_geometry(geom, return_shapely=True)
            geo_dict, shp = result
        else:
            geo_dict = _sanitize_geometry(geom)
            shp = None

        if geo_dict is not None:
            sanitized_geojsons.append(geo_dict)
            sanitized_shapely.append(shp)
            valid_indices.append(i)

    if not valid_indices:
        return 0

    # Calcular áreas
    if has_source_area:
        source_areas = gdf["area_in_meters"].values
        areas = [round(float(source_areas[idx]), 2) if source_areas[idx] == source_areas[idx] else 0.0
                 for idx in valid_indices]
    else:
        areas = []
        for shp in sanitized_shapely:
            a, _ = _GEOD.geometry_area_perimeter(shp)
            areas.append(round(abs(a), 2))

    confidences = gdf["confidence"].values if has_conf else None

    # Construir documentos y flush en batches
    inserted = 0
    batch = []

    for i, orig_idx in enumerate(valid_indices):
        doc = {
            "geometry":    sanitized_geojsons[i],
            "area_m2":     areas[i],
            "source":      dataset_type,
            "ingested_at": now,
        }
        if has_conf:
            c = confidences[orig_idx]
            if c == c:
                doc["confidence_score"] = float(c)

        batch.append(doc)

        if len(batch) >= CHUNK_SIZE:
            inserted += _flush_chunk(collection, batch)
            batch = []

    if batch:
        inserted += _flush_chunk(collection, batch)

    return inserted


# ═══════════════════════════════════════════════════════════════
# Index management
# ═══════════════════════════════════════════════════════════════

def _clean_invalid_documents(db, col_name: str):
    """Elimina documentos con geometrías incompatibles con 2dsphere."""
    collection = db[col_name]
    invalid_ids = []
    for doc in collection.find({"geometry": {"$exists": True}}, {"_id": 1, "geometry": 1}).batch_size(5000):
        geom = doc.get("geometry")
        if geom is None:
            invalid_ids.append(doc["_id"])
            continue
        gtype = geom.get("type", "")
        if gtype not in ("Polygon", "MultiPolygon"):
            invalid_ids.append(doc["_id"])
            continue
        if not geom.get("coordinates"):
            invalid_ids.append(doc["_id"])

    if invalid_ids:
        result = collection.delete_many({"_id": {"$in": invalid_ids}})
        print(f"  Limpieza: {result.deleted_count} documentos invalidos eliminados de '{col_name}'.")
    return len(invalid_ids)


def ensure_spatial_indexes(db, col_name: str):
    """Crea el índice 2dsphere con fallback de reparación automática."""
    print(f"-> Asegurando indice 2dsphere en '{col_name}'...")
    try:
        db[col_name].create_index([("geometry", GEOSPHERE)])
        print(f"   Indexacion exitosa en '{col_name}'\n")
    except OperationFailure as e:
        error_msg = str(e)
        if "Loop" in error_msg or "valid loop" in error_msg or "Edges" in error_msg or "GeoJSON" in error_msg:
            print(f"   Fallo por geometrias invalidas. Reparando...")
            _clean_invalid_documents(db, col_name)
            _repair_collection_geometries(db, col_name)
            db[col_name].create_index([("geometry", GEOSPHERE)])
            print(f"   Indexacion exitosa en '{col_name}' (post-reparacion)\n")
        else:
            raise


def _repair_collection_geometries(db, col_name: str):
    """Recorre la colección y repara/normaliza geometrías in-place."""
    collection = db[col_name]
    repaired = 0
    removed = 0
    batch_ops = []

    cursor = collection.find({}, {"_id": 1, "geometry": 1}).batch_size(2000)
    for doc in cursor:
        raw_geom = doc.get("geometry")
        if raw_geom is None:
            batch_ops.append(("delete", doc["_id"]))
            continue
        try:
            shp = shape(raw_geom)
        except Exception:
            batch_ops.append(("delete", doc["_id"]))
            continue

        sanitized = _sanitize_geometry(shp)
        if sanitized is None:
            batch_ops.append(("delete", doc["_id"]))
        elif sanitized != raw_geom:
            batch_ops.append(("update", doc["_id"], sanitized))

        if len(batch_ops) >= 1000:
            r, d = _flush_repair_ops(collection, batch_ops)
            repaired += r
            removed += d
            batch_ops = []

    if batch_ops:
        r, d = _flush_repair_ops(collection, batch_ops)
        repaired += r
        removed += d

    if repaired or removed:
        print(f"  Reparacion: {repaired} corregidas, {removed} eliminadas en '{col_name}'.")


def _flush_repair_ops(collection, ops) -> tuple:
    """Ejecuta batch de reparación."""
    bulk = []
    repaired = 0
    removed = 0
    for op in ops:
        if op[0] == "delete":
            bulk.append(DeleteOne({"_id": op[1]}))
            removed += 1
        elif op[0] == "update":
            bulk.append(UpdateOne({"_id": op[1]}, {"$set": {"geometry": op[2]}}))
            repaired += 1
    if bulk:
        collection.bulk_write(bulk, ordered=False)
    return repaired, removed


# ═══════════════════════════════════════════════════════════════
# MongoDB connection check
# ═══════════════════════════════════════════════════════════════

def _check_mongo_connection(uri: str):
    """Verifica que MongoDB sea alcanzable."""
    client = MongoClient(uri, serverSelectionTimeoutMS=5_000)
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        raise RuntimeError(
            f"\nNo se puede conectar a MongoDB en: {uri}\n"
            "Verifica que el servicio este corriendo.\n"
            "  docker start upme-mongo\n"
            "  o: net start MongoDB"
        )
    finally:
        client.close()


# ═══════════════════════════════════════════════════════════════
# Main ingestion entry points
# ═══════════════════════════════════════════════════════════════

def run_buildings_ingestion(file_path: str, dataset_type: str):
    """
    Ingesta optimizada de huellas de edificios.
    Optimizaciones vs versión anterior:
    - Streaming en chunks (sin MemoryError en particiones grandes)
    - Prefilter por bounding box (salta particiones fuera del area PDET)
    - Prepared geometry para intersects ~10x mas rapido
    - Batch inserts de 10k documentos
    """
    _check_mongo_connection(MONGO_URI)
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col_name = f"buildings_{dataset_type}"
    # Write concern w:0 para ingesta masiva (fire-and-forget, ~30-40% más rápido)
    collection = db[col_name].with_options(write_concern=WriteConcern(w=0))

    now = datetime.now(timezone.utc)
    inserted = 0

    print(f"\nCargando datos de {dataset_type.upper()}...")
    pdet_bbox, pdet_tree, _ = _load_pdet_filter()

    if dataset_type == "microsoft":
        files = sorted([
            os.path.join(file_path, f)
            for f in os.listdir(file_path)
            if f.endswith(".csv.gz")
        ])
        if not files:
            raise FileNotFoundError(f"No se encontraron archivos .csv.gz en '{file_path}'")

        done = _load_progress(dataset_type)
        total_files = len(files)
        pending = [fp for fp in files if os.path.basename(fp) not in done]
        skipped_done = total_files - len(pending)

        print(f"  {total_files} particiones totales -- "
              f"{skipped_done} ya cargadas, {len(pending)} pendientes.")

        # Prefilter: determinar cuales particiones intersectan el area PDET
        print(f"  Prefiltro por bounding box...")
        relevant = []
        skipped_bbox = 0
        for fp in pending:
            if _partition_intersects_pdet(fp, pdet_bbox):
                relevant.append(fp)
            else:
                skipped_bbox += 1
                done.add(os.path.basename(fp))

        if skipped_bbox > 0:
            _save_progress(dataset_type, done)
            print(f"  {skipped_bbox} particiones fuera del area PDET (saltadas).")
        print(f"  {len(relevant)} particiones relevantes a procesar.\n")

        pdet_bounds = pdet_bbox.bounds  # (minx, miny, maxx, maxy)

        for i, fp in enumerate(relevant, 1):
            name = os.path.basename(fp)
            partition_rows = 0
            partition_ins = 0

            for gdf_chunk in _iter_ms_partition(fp, pdet_bounds=pdet_bounds):
                n = _ingest_gdf(gdf_chunk, collection, dataset_type, now,
                                pdet_tree, pdet_bbox)
                partition_rows += len(gdf_chunk)
                partition_ins += n
                inserted += n
                del gdf_chunk

            done.add(name)
            _save_progress(dataset_type, done)
            print(f"  [{skipped_done + i}/{total_files}] {name} "
                  f"-- {partition_rows:,} filas, {partition_ins:,} insertados "
                  f"(total: {inserted:,})")

    else:  # google
        files = sorted([
            os.path.join(file_path, f)
            for f in os.listdir(file_path)
            if f.endswith(".csv.gz")
        ])
        if not files:
            raise FileNotFoundError(f"No se encontraron tiles .csv.gz en '{file_path}'")

        done = _load_progress(dataset_type)
        total_files = len(files)
        pending = [fp for fp in files if os.path.basename(fp) not in done]
        skipped_done = total_files - len(pending)

        print(f"  {total_files} tiles totales -- {skipped_done} ya cargados, {len(pending)} pendientes.\n")

        for i, fp in enumerate(pending, 1):
            name = os.path.basename(fp)
            tile_rows = 0
            tile_ins = 0
            print(f"  [{skipped_done + i}/{total_files}] {name} ...", flush=True)
            for gdf_chunk in _iter_google_tile(fp, pdet_bounds=pdet_bbox.bounds):
                n = _ingest_gdf(gdf_chunk, collection, dataset_type, now,
                                pdet_tree, pdet_bbox)
                tile_rows += len(gdf_chunk)
                tile_ins += n
                inserted += n
                del gdf_chunk
            import gc; gc.collect()
            done.add(name)
            _save_progress(dataset_type, done)
            print(f"  [{skipped_done + i}/{total_files}] {name} "
                  f"-- {tile_rows:,} filas, {tile_ins:,} insertados "
                  f"(total: {inserted:,})")

    print("\nCreando indice 2dsphere...")
    ensure_spatial_indexes(db, col_name)

    print(f"\n  Ingesta completada: {inserted:,} documentos insertados en esta sesion.\n")
    client.close()


def run_repair_and_reindex():
    """Repara geometrías existentes y recrea índices 2dsphere."""
    _check_mongo_connection(MONGO_URI)
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print("\n" + "="*60)
    print(" REPARACION Y REINDEXACION DE COLECCIONES DE EDIFICIOS")
    print("="*60)

    for dataset_type in ["microsoft", "google"]:
        col_name = f"buildings_{dataset_type}"
        collection = db[col_name]
        count = collection.count_documents({})
        if count == 0:
            print(f"\n  [{col_name}] Coleccion vacia, se omite.")
            continue

        print(f"\n  [{col_name}] {count:,} documentos encontrados.")

        for idx in collection.list_indexes():
            key = idx.get("key", {})
            if "2dsphere" in str(key):
                print(f"    Eliminando indice: {idx['name']}")
                collection.drop_index(idx["name"])

        print(f"    Reparando geometrias...")
        _repair_collection_geometries(db, col_name)

        print(f"    Recreando indice 2dsphere...")
        ensure_spatial_indexes(db, col_name)

    print("\n  Reparacion completada.\n")
    client.close()
