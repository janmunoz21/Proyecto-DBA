import geopandas as gpd
from pymongo import MongoClient, GEOSPHERE
from datetime import datetime, timezone

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "upme-project"


def ensure_spatial_indexes(db, col_name: str):

    # Crea un índice geoespacial 2dsphere de manera preventiva 
    # esto asegura que las consultas geoespaciales sean eficientes
    print(f"-> Asegurando índice geoespacial 2dsphere en la coleccion '{col_name}'...")
    db[col_name].create_index([("geometry", GEOSPHERE)])
    print(f" Indexación exitosa en '{col_name}'\n")


def run_buildings_ingestion(file_path: str, dataset_type: str):
    """
    Lee las huellas geográficas, calcula el área en m2 de los techos
    y aplica upsert en colecciones NoSQL separadas para cada dataset de edificios
    """
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col_name = f"buildings_{dataset_type}"
    collection = db[col_name]
    
    # Validar índices primero
    ensure_spatial_indexes(db, col_name)
    
    print(f"\nProcesando archivo geográfico en GeoPandas: {file_path}")
    gdf = gpd.read_file(file_path)
    
    # Validar el Sistema de Referencia de Coordenadas para MongoDB (Debe ser EPSG:4326)
    if gdf.crs != "EPSG:4326":
        print("-> Reproyectando capas espaciales a WGS84 (EPSG:4326)...")
        gdf = gdf.to_crs(epsg=4326)
        
    documents = []
    print("Transformando registros al esquema flexible NoSQL...")
    
    for _, row in gdf.iterrows():
        geom = row['geometry']
        if geom is None or geom.is_empty:
            continue
            
        # Calcular el área del footprint en metros cuadrados utilizando la geometría plana
        # Si el archivo original viene proyectado se usa directo, de lo contrario se calcula un estimado
        area_m2 = geom.area if gdf.crs.is_projected else geom.area * (111111 ** 2)
        
        # Mapeo del esquema base documentado en la arquitectura
        doc = {
            "geometry": geom.__geo_interface__,  # Conversión nativa a estructura GeoJSON
            "area_m2": round(float(area_m2), 2),
            "dataset_source": dataset_type,
            "ingested_at": datetime.now(timezone.utc)
        }
        
        # Esquema Flexible: Atributo exclusivo del dataset de Google Open Buildings
        if dataset_type == "google" and "confidence" in row:
            doc["confidence_score"] = float(row["confidence"])
            
        documents.append(doc)
        
    if documents:
        print(f"Escribiendo {len(documents)} registros de manera masiva en la coleccion...")
        # Inserción masiva para optimizar los tiempos de I/O
        collection.insert_many(documents)
        print(f" Ingesta completada con éxito para {dataset_type}.\n")
    else:
        print(" No se extrajeron registros geoespaciales válidos.\n")
        
    client.close()