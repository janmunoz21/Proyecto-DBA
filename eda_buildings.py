import json
from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "upme-project"

DATASETS = ["microsoft", "google"]


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _section(title: str):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


def _subsection(title: str):
    print(f"\n  {'─'*54}")
    print(f"  {title}")
    print(f"  {'─'*54}")


def _pct(part: int, total: int) -> str:
    if total == 0:
        return "0.00%"
    return f"{part / total * 100:.2f}%"


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
        status = "✓" if count > 0 else "✗ VACÍA"
        print(f"  buildings_{ds:<12} : {count:>12,} documentos  [{status}]")

    return counts


# ──────────────────────────────────────────────────────────────
# 2. Estadísticas de área (area_m2)
# ──────────────────────────────────────────────────────────────

def audit_area_stats(db) -> dict:
    """Calcula estadísticas descriptivas de area_m2 para cada dataset."""
    _section("2. ESTADÍSTICAS DE ÁREA (area_m2 en m²)")

    all_stats = {}
    for ds in DATASETS:
        col = db[f"buildings_{ds}"]
        if col.count_documents({}) == 0:
            print(f"\n  [buildings_{ds}] — colección vacía, se omite.\n")
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
        print(f"    Área total      : {s['total']:>15,.2f} m²")
        print(f"    Media           : {s['mean']:>12,.2f} m²")
        print(f"    Desv. estándar  : {s['stddev']:>12,.2f} m²")
        print(f"    Mínimo          : {s['min']:>12,.2f} m²")
        print(f"    Máximo          : {s['max']:>12,.2f} m²")

        # Percentiles mediante $bucketAuto (5 cubetas)
        p_pipeline = [
            {"$bucketAuto": {
                "groupBy": "$area_m2",
                "buckets": 5,
                "output":  {"count": {"$sum": 1}}
            }}
        ]
        buckets = list(col.aggregate(p_pipeline))
        print(f"\n    Distribución por quintil:")
        print(f"    {'Rango (m²)':<35} {'Conteo':>10}")
        for b in buckets:
            lo = b["_id"]["min"]
            hi = b["_id"]["max"]
            print(f"    [{lo:>10.2f} — {hi:>10.2f}]   {b['count']:>10,}")

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
        no_source   = col.count_documents({"dataset_source": {"$exists": False}})

        print(f"    {'Problema':<35} {'Conteo':>8}   {'% del total':>10}")
        print(f"    {'─'*57}")
        print(f"    {'area_m2 nula':<35} {null_area:>8,}   {_pct(null_area, total):>10}")
        print(f"    {'area_m2 <= 0':<35} {zero_area:>8,}   {_pct(zero_area, total):>10}")
        print(f"    {'geometry ausente':<35} {null_geom:>8,}   {_pct(null_geom, total):>10}")
        print(f"    {'sin dataset_source':<35} {no_source:>8,}   {_pct(no_source, total):>10}")


# ──────────────────────────────────────────────────────────────
# 4. Campo exclusivo Google: confidence_score
# ──────────────────────────────────────────────────────────────

def audit_google_confidence(db):
    """Analiza la distribución de confidence_score para Google Open Buildings."""
    col = db["buildings_google"]
    if col.count_documents({}) == 0:
        return

    _section("4. CONFIDENCE SCORE — Google Open Buildings")

    total = col.count_documents({})
    with_score = col.count_documents({"confidence_score": {"$exists": True, "$ne": None}})
    without    = total - with_score

    print(f"  Registros con confidence_score  : {with_score:>10,}  ({_pct(with_score, total)})")
    print(f"  Registros sin confidence_score  : {without:>10,}  ({_pct(without, total)})")

    if with_score == 0:
        return

    pipeline = [
        {"$match": {"confidence_score": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": None,
            "mean": {"$avg": "$confidence_score"},
            "min":  {"$min": "$confidence_score"},
            "max":  {"$max": "$confidence_score"},
        }}
    ]
    r = list(col.aggregate(pipeline))
    if r:
        s = r[0]
        print(f"\n  Media  : {s['mean']:.4f}")
        print(f"  Mínimo : {s['min']:.4f}")
        print(f"  Máximo : {s['max']:.4f}")

    # Distribución en cubetas fijas: < 0.6, 0.6–0.7, 0.7–0.8, 0.8–0.9, >= 0.9
    thresholds = [
        ("< 0.60",  {"$lt": 0.6}),
        ("0.60–0.70", {"$gte": 0.6, "$lt": 0.7}),
        ("0.70–0.80", {"$gte": 0.7, "$lt": 0.8}),
        ("0.80–0.90", {"$gte": 0.8, "$lt": 0.9}),
        (">= 0.90",  {"$gte": 0.9}),
    ]
    print(f"\n  {'Rango':<15} {'Conteo':>10}   {'%':>8}")
    print(f"  {'─'*37}")
    for label, filt in thresholds:
        n = col.count_documents({"confidence_score": filt})
        print(f"  {label:<15} {n:>10,}   {_pct(n, with_score):>8}")


# ──────────────────────────────────────────────────────────────
# 5. Índices registrados
# ──────────────────────────────────────────────────────────────

def audit_indexes(db):
    """Lista los índices creados en cada colección de edificios."""
    _section("5. ÍNDICES EN MONGODB")

    for ds in DATASETS:
        col_name = f"buildings_{ds}"
        col = db[col_name]
        indexes = list(col.list_indexes())
        print(f"\n  buildings_{ds}:")
        for idx in indexes:
            print(f"    • {idx['name']:<30}  key: {dict(idx['key'])}")


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
            print("  [colección vacía]")


# ──────────────────────────────────────────────────────────────
# 7. Tabla comparativa final
# ──────────────────────────────────────────────────────────────

def print_comparison(db, counts: dict, stats: dict):
    """Tabla resumen comparando ambos datasets."""
    _section("7. TABLA COMPARATIVA MICROSOFT vs GOOGLE")

    header = f"  {'Métrica':<30} {'Microsoft':>15} {'Google':>15}"
    print(header)
    print(f"  {'─'*62}")

    def row(label, ms_val, g_val):
        print(f"  {label:<30} {ms_val:>15} {g_val:>15}")

    ms_count = counts.get("microsoft", 0)
    g_count  = counts.get("google", 0)
    row("Total documentos", f"{ms_count:,}", f"{g_count:,}")

    ms_s = stats.get("microsoft")
    g_s  = stats.get("google")

    def fmt(val, decimals=2):
        return f"{val:,.{decimals}f}" if val is not None else "N/A"

    row("Área media (m²)",
        fmt(ms_s["mean"]) if ms_s else "N/A",
        fmt(g_s["mean"])  if g_s  else "N/A")
    row("Área mínima (m²)",
        fmt(ms_s["min"])  if ms_s else "N/A",
        fmt(g_s["min"])   if g_s  else "N/A")
    row("Área máxima (m²)",
        fmt(ms_s["max"])  if ms_s else "N/A",
        fmt(g_s["max"])   if g_s  else "N/A")
    row("Desv. estándar (m²)",
        fmt(ms_s["stddev"]) if ms_s else "N/A",
        fmt(g_s["stddev"])  if g_s  else "N/A")
    row("Área total acumulada (m²)",
        fmt(ms_s["total"], 0) if ms_s else "N/A",
        fmt(g_s["total"], 0)  if g_s  else "N/A")

    # Índice 2dsphere presente
    def has_2dsphere(col_name):
        idxs = list(db[col_name].list_indexes())
        return any("2dsphere" in str(i.get("key", {})) for i in idxs)

    row("Índice 2dsphere",
        "✓ Sí" if has_2dsphere("buildings_microsoft") else "✗ No",
        "✓ Sí" if has_2dsphere("buildings_google")    else "✗ No")


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def run_eda():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print("\n" + "="*60)
    print(" EDA — BUILDING FOOTPRINTS (Microsoft & Google)")
    print(" Base de datos: " + DB_NAME)
    print("="*60)

    counts = audit_collection_counts(db)
    stats  = audit_area_stats(db)
    audit_data_quality(db, counts)
    audit_google_confidence(db)
    audit_indexes(db)
    audit_sample_documents(db)
    print_comparison(db, counts, stats)

    print(f"\n{'='*60}")
    print(" EDA completado.")
    print("="*60 + "\n")

    client.close()


if __name__ == "__main__":
    run_eda()
