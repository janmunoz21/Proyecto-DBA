import json
from datetime import datetime, timezone

from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "upme-project"
RESULTS_COLLECTION = "analysis_results"

DATASETS = ["microsoft", "google"]


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _section(title: str):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


def _subsection(title: str):
    print(f"\n  {'-'*54}")
    print(f"  {title}")
    print(f"  {'-'*54}")


def _pct(part: int, total: int) -> str:
    if total == 0:
        return "0.00%"
    return f"{part / total * 100:.2f}%"


def _google_confidence_field(col) -> str | None:
    """Detecta el campo de confianza disponible para Google, con compatibilidad hacia atrás."""
    if col.count_documents({"confidence_score": {"$exists": True, "$ne": None}}) > 0:
        return "confidence_score"
    if col.count_documents({"confidence": {"$exists": True, "$ne": None}}) > 0:
        return "confidence"
    return None


# ──────────────────────────────────────────────────────────────
# 1. Conteo y existencia de colecciones
# ──────────────────────────────────────────────────────────────

def audit_collection_counts(db) -> dict:
    """Cuenta documentos por colección y detecta colecciones vacías o inexistentes."""
    _section("1. CONTEO DE DOCUMENTOS POR DATASET")

    counts = {}
    for ds in DATASETS:
        col_name = f"buildings_{ds}"
        count = db[col_name].count_documents({})
        counts[ds] = count
        status = "OK" if count > 0 else "VACIA"
        print(f"  buildings_{ds:<12} : {count:>12,} documentos  [{status}]")

    return counts


# ──────────────────────────────────────────────────────────────
# 2. Estadísticas de área (area_m2)
# ──────────────────────────────────────────────────────────────

def audit_area_stats(db) -> dict:
    """Calcula estadísticas descriptivas de area_m2 para cada dataset."""
    _section("2. ESTADISTICAS DE AREA (area_m2 en m2)")

    all_stats = {}
    for ds in DATASETS:
        col = db[f"buildings_{ds}"]
        if col.count_documents({}) == 0:
            print(f"\n  [buildings_{ds}] -- coleccion vacia, se omite.\n")
            continue

        _subsection(f"Dataset: {ds.upper()}")

        pipeline = [
            {"$group": {
                "_id": None,
                "count":  {"$sum": 1},
                "mean":   {"$avg": "$area_m2"},
                "min":    {"$min": "$area_m2"},
                "max":    {"$max": "$area_m2"},
                "stddev": {"$stdDevPop": "$area_m2"},
                "total":  {"$sum": "$area_m2"},
            }}
        ]
        result = list(col.aggregate(pipeline))
        if not result:
            continue

        s = result[0]
        print(f"    Conteo          : {s['count']:>12,}")
        print(f"    Area total      : {s['total']:>15,.2f} m2")
        print(f"    Media           : {s['mean']:>12,.2f} m2")
        print(f"    Desv. estandar  : {s['stddev']:>12,.2f} m2")
        print(f"    Minimo          : {s['min']:>12,.2f} m2")
        print(f"    Maximo          : {s['max']:>12,.2f} m2")

        # Percentiles mediante $bucketAuto (5 cubetas)
        p_pipeline = [
            {"$bucketAuto": {
                "groupBy": "$area_m2",
                "buckets": 5,
                "output":  {"count": {"$sum": 1}}
            }}
        ]
        buckets = list(col.aggregate(p_pipeline))
        print(f"\n    Distribucion por quintil:")
        print(f"    {'Rango (m2)':<35} {'Conteo':>10}")
        for b in buckets:
            lo = b["_id"]["min"]
            hi = b["_id"]["max"]
            print(f"    [{lo:>10.2f} - {hi:>10.2f}]   {b['count']:>10,}")

        all_stats[ds] = s

    return all_stats


# ──────────────────────────────────────────────────────────────
# 3. Calidad de datos: nulos, cero, geometría ausente
# ──────────────────────────────────────────────────────────────

def audit_data_quality(db, counts: dict):
    """Detecta registros con area_m2 nula, cero o geometría ausente."""
    _section("3. CALIDAD DE DATOS")

    for ds in DATASETS:
        col = db[f"buildings_{ds}"]
        total = counts.get(ds, 0)
        if total == 0:
            continue

        _subsection(f"Dataset: {ds.upper()}")

        null_area   = col.count_documents({"area_m2": None})
        zero_area   = col.count_documents({"area_m2": {"$lte": 0}})
        null_geom   = col.count_documents({"geometry": None})
        no_source   = col.count_documents({"source": {"$exists": False}})

        print(f"    {'Problema':<35} {'Conteo':>8}   {'% del total':>10}")
        print(f"    {'-'*57}")
        print(f"    {'area_m2 nula':<35} {null_area:>8,}   {_pct(null_area, total):>10}")
        print(f"    {'area_m2 <= 0':<35} {zero_area:>8,}   {_pct(zero_area, total):>10}")
        print(f"    {'geometry ausente':<35} {null_geom:>8,}   {_pct(null_geom, total):>10}")
        print(f"    {'sin source':<35} {no_source:>8,}   {_pct(no_source, total):>10}")


# ──────────────────────────────────────────────────────────────
# 4. Campo exclusivo Google: confidence_score
# ──────────────────────────────────────────────────────────────

def audit_google_confidence(db):
    """Analiza la distribución de confidence_score para Google Open Buildings."""
    col = db["buildings_google"]
    if col.count_documents({}) == 0:
        return

    _section("4. CONFIDENCE SCORE - Google Open Buildings")

    total = col.count_documents({})
    confidence_field = _google_confidence_field(col)
    if confidence_field is None:
        print("  No se encontro confidence_score ni confidence en la coleccion.")
        return

    with_score = col.count_documents({confidence_field: {"$exists": True, "$ne": None}})
    without    = total - with_score

    print(f"  Registros con {confidence_field:<15}: {with_score:>10,}  ({_pct(with_score, total)})")
    print(f"  Registros sin {confidence_field:<15}: {without:>10,}  ({_pct(without, total)})")

    if with_score == 0:
        return

    pipeline = [
        {"$match": {confidence_field: {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": None,
            "mean": {"$avg": f"${confidence_field}"},
            "min":  {"$min": f"${confidence_field}"},
            "max":  {"$max": f"${confidence_field}"},
        }}
    ]
    r = list(col.aggregate(pipeline))
    if r:
        s = r[0]
        print(f"\n  Media  : {s['mean']:.4f}")
        print(f"  Minimo : {s['min']:.4f}")
        print(f"  Maximo : {s['max']:.4f}")

    thresholds = [
        ("< 0.60",    {"$lt": 0.6}),
        ("0.60-0.70", {"$gte": 0.6, "$lt": 0.7}),
        ("0.70-0.80", {"$gte": 0.7, "$lt": 0.8}),
        ("0.80-0.90", {"$gte": 0.8, "$lt": 0.9}),
        (">= 0.90",  {"$gte": 0.9}),
    ]
    print(f"\n  {'Rango':<15} {'Conteo':>10}   {'%':>8}")
    print(f"  {'-'*37}")
    for label, filt in thresholds:
        n = col.count_documents({confidence_field: filt})
        print(f"  {label:<15} {n:>10,}   {_pct(n, with_score):>8}")


# ──────────────────────────────────────────────────────────────
# 5. Índices registrados
# ──────────────────────────────────────────────────────────────

def audit_indexes(db):
    """Lista los índices creados en cada colección de edificios."""
    _section("5. INDICES EN MONGODB")

    for ds in DATASETS:
        col_name = f"buildings_{ds}"
        col = db[col_name]
        indexes = list(col.list_indexes())
        print(f"\n  buildings_{ds}:")
        for idx in indexes:
            print(f"    - {idx['name']:<30}  key: {dict(idx['key'])}")


# ──────────────────────────────────────────────────────────────
# 6. Muestra de documentos
# ──────────────────────────────────────────────────────────────

def audit_sample_documents(db):
    """Muestra un documento representativo de cada dataset."""
    _section("6. MUESTRA DE DOCUMENTOS")

    projection = {"_id": 0, "geometry": 0}  # omitir coordenadas para legibilidad

    for ds in DATASETS:
        col = db[f"buildings_{ds}"]
        doc = col.find_one({}, projection)
        _subsection(f"Dataset: {ds.upper()}")
        if doc:
            print(json.dumps(doc, indent=4, default=str))
        else:
            print("  [coleccion vacia]")


# ──────────────────────────────────────────────────────────────
# 7. Análisis geoespacial por municipio
# ──────────────────────────────────────────────────────────────

def _ensure_results_index(results_col):
    results_col.create_index([("municipality_code", 1), ("dataset", 1)], unique=True)


def _aggregate_municipality_for_dataset(db, municipality: dict, dataset: str) -> dict:
    buildings = db[f"buildings_{dataset}"]
    municipality_geom = municipality["geometry"]

    pipeline = [
        {"$match": {"geometry": {"$geoWithin": {"$geometry": municipality_geom}}}},
        {"$group": {
            "_id": None,
            "building_count": {"$sum": 1},
            "total_area_m2": {"$sum": "$area_m2"},
            "avg_area_m2": {"$avg": "$area_m2"},
        }},
    ]

    result = list(buildings.aggregate(pipeline, allowDiskUse=True))
    metrics = result[0] if result else {"building_count": 0, "total_area_m2": 0, "avg_area_m2": 0}

    return {
        "municipality_code": municipality["dane_code"],
        "municipality_name": municipality.get("name"),
        "department": municipality.get("department"),
        "dataset": dataset,
        "building_count": int(metrics.get("building_count", 0) or 0),
        "total_area_m2": float(metrics.get("total_area_m2", 0) or 0),
        "avg_area_m2": float(metrics.get("avg_area_m2", 0) or 0),
        "computed_at": datetime.now(timezone.utc),
    }


def run_spatial_analysis(db):
    """Calcula y persiste conteos y áreas por municipio para cada dataset."""
    municipalities = list(db["municipalities"].find({"is_pdet": True}, {"_id": 0}))
    if not municipalities:
        print("\nNo hay municipios PDET cargados; se omite el analisis geoespacial.")
        return []

    results_col = db[RESULTS_COLLECTION]
    _ensure_results_index(results_col)

    print("\n" + "=" * 60)
    print(" 7. ANALISIS GEOESPACIAL Y AGREGACIONES")
    print("=" * 60)

    inserted = []
    for dataset in DATASETS:
        print(f"\n  Procesando dataset: {dataset.upper()}")
        dataset_results = []
        for municipality in municipalities:
            doc = _aggregate_municipality_for_dataset(db, municipality, dataset)
            results_col.update_one(
                {"municipality_code": doc["municipality_code"], "dataset": doc["dataset"]},
                {"$set": doc},
                upsert=True,
            )
            dataset_results.append(doc)
            inserted.append(doc)

        total_buildings = sum(item["building_count"] for item in dataset_results)
        total_area = sum(item["total_area_m2"] for item in dataset_results)
        print(f"    Municipios procesados : {len(dataset_results):,}")
        print(f"    Edificios totales     : {total_buildings:,}")
        print(f"    Area total acumulada  : {total_area:,.2f} m2")

    print(f"\n  Resultados almacenados en '{RESULTS_COLLECTION}'.")
    return inserted


# ──────────────────────────────────────────────────────────────
# 8. Top municipios por área
# ──────────────────────────────────────────────────────────────

def print_top_municipalities(db, top_n: int = 10):
    """Imprime los municipios con mayor área total de techos por dataset."""
    results_col = db[RESULTS_COLLECTION]
    if results_col.count_documents({}) == 0:
        return

    _section(f"8. TOP {top_n} MUNICIPIOS POR AREA DE TECHOS")

    for dataset in DATASETS:
        _subsection(f"Dataset: {dataset.upper()}")
        pipeline = [
            {"$match": {"dataset": dataset, "building_count": {"$gt": 0}}},
            {"$sort": {"total_area_m2": -1}},
            {"$limit": top_n},
            {"$project": {"_id": 0, "municipality_name": 1, "department": 1,
                          "building_count": 1, "total_area_m2": 1, "avg_area_m2": 1}},
        ]
        results = list(results_col.aggregate(pipeline))
        if not results:
            print("    Sin resultados de analisis. Ejecuta primero la opcion 6.")
            continue

        print(f"    {'#':<4} {'Municipio':<25} {'Depto':<18} {'Edif.':>8} {'Area total m2':>14} {'Area prom m2':>12}")
        print(f"    {'-'*85}")
        for i, r in enumerate(results, 1):
            print(f"    {i:<4} {r.get('municipality_name',''):<25} "
                  f"{r.get('department',''):<18} "
                  f"{r['building_count']:>8,} "
                  f"{r['total_area_m2']:>14,.2f} "
                  f"{r['avg_area_m2']:>12,.2f}")


# ──────────────────────────────────────────────────────────────
# 9. Tabla comparativa final
# ──────────────────────────────────────────────────────────────

def print_comparison(db, counts: dict, stats: dict):
    """Tabla resumen comparando ambos datasets."""
    _section("9. TABLA COMPARATIVA MICROSOFT vs GOOGLE")

    header = f"  {'Metrica':<30} {'Microsoft':>15} {'Google':>15}"
    print(header)
    print(f"  {'-'*62}")

    def row(label, ms_val, g_val):
        print(f"  {label:<30} {ms_val:>15} {g_val:>15}")

    ms_count = counts.get("microsoft", 0)
    g_count  = counts.get("google", 0)
    row("Total documentos", f"{ms_count:,}", f"{g_count:,}")

    ms_s = stats.get("microsoft")
    g_s  = stats.get("google")

    def fmt(val, decimals=2):
        return f"{val:,.{decimals}f}" if val is not None else "N/A"

    row("Area media (m2)",
        fmt(ms_s["mean"]) if ms_s else "N/A",
        fmt(g_s["mean"])  if g_s  else "N/A")
    row("Area minima (m2)",
        fmt(ms_s["min"])  if ms_s else "N/A",
        fmt(g_s["min"])   if g_s  else "N/A")
    row("Area maxima (m2)",
        fmt(ms_s["max"])  if ms_s else "N/A",
        fmt(g_s["max"])   if g_s  else "N/A")
    row("Desv. estandar (m2)",
        fmt(ms_s["stddev"]) if ms_s else "N/A",
        fmt(g_s["stddev"])  if g_s  else "N/A")
    row("Area total acumulada (m2)",
        fmt(ms_s["total"], 0) if ms_s else "N/A",
        fmt(g_s["total"], 0)  if g_s  else "N/A")

    # Indice 2dsphere presente
    def has_2dsphere(col_name):
        idxs = list(db[col_name].list_indexes())
        return any("2dsphere" in str(i.get("key", {})) for i in idxs)

    row("Indice 2dsphere",
        "Si" if has_2dsphere("buildings_microsoft") else "No",
        "Si" if has_2dsphere("buildings_google")    else "No")


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def run_spatial_analysis_standalone():
    """Entry point para ejecutar solo el análisis geoespacial (opción 6 del menú)."""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print("\n" + "="*60)
    print(" SEMANA 4 - ANALISIS GEOESPACIAL POR MUNICIPIO")
    print(" Base de datos: " + DB_NAME)
    print("="*60)

    run_spatial_analysis(db)
    print_top_municipalities(db)

    print(f"\n{'='*60}")
    print(" Analisis geoespacial completado.")
    print("="*60 + "\n")

    client.close()


def run_eda():
    """EDA completa: auditoría + análisis geoespacial + comparativa."""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print("\n" + "="*60)
    print(" EDA - BUILDING FOOTPRINTS (Microsoft & Google)")
    print(" Base de datos: " + DB_NAME)
    print("="*60)

    counts = audit_collection_counts(db)
    stats  = audit_area_stats(db)
    audit_data_quality(db, counts)
    audit_google_confidence(db)
    audit_indexes(db)
    audit_sample_documents(db)
    run_spatial_analysis(db)
    print_top_municipalities(db)
    print_comparison(db, counts, stats)

    print(f"\n{'='*60}")
    print(" EDA completado.")
    print("="*60 + "\n")

    client.close()


if __name__ == "__main__":
    run_eda()
