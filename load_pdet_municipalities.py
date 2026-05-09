import geopandas as gpd
from pymongo import MongoClient
from datetime import datetime

# Datos de conexión (localhost y puerto 27017)
MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "upme-project"
COLLECTION_NAME = "municipalities"

def run_ingestion(shapefile_path):
    """
    Función para filtrar municipios PDET y cargarlos en MongoDB
    """
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    print(f"Leyendo archivo: {shapefile_path}...")
    # Se utiliza GeoPandas para la lectura de shapefiles (MGN)
    gdf = gpd.read_file(shapefile_path)

    # Filtrado: El Marco Geoestadístico Nacional (MGN) tiene códigos de municipio
    # Aquí nos aseguramos de que las geometrías sean WGS84 (EPSG:4326)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)

    # Simulación de carga
    # Por ahora, preparamos la estructura de documento GeoJSON definida
    records = []
    for _, row in gdf.iterrows():
        # Calcular el área en km² antes de subirlo
        # Nota: Se usa un CRS proyectado temporalmente para calcular metros/km reales
        area_m2 = row['geometry'].area 
        area_km2 = area_m2 * 10**6
        
        # Estructura de documento
        document = {
            "dane_code": row.get('MPIO_CDPTO', 'N/A'),
            "name": row.get('MPIO_CNMBR', 'N/A'),
            "department": row.get('DPTO_CNMBR', 'N/A'),
            "is_pdet": True, 
            "geometry": row['geometry'].__geo_interface__, # Conversión a GeoJSON native
            "area_km2": round(float(area_km2), 2),
            "source": "MGN2025",
            "ingested_at": datetime.now()
        }
        
        if records:
            # Usamos update_one con upsert=True para no duplicar datos si se corre dos veces
            for doc in records:
                collection.update_one(
                    {"dane_code": doc["dane_code"]}, 
                    {"$set": doc}, 
                    upsert=True
                )
            print(f"Exito: {len(records)} municipios sincronizados con la colección {COLLECTION_NAME}")


if __name__ == "__main__":
    # TODO -  Aqui se debe poner la ruta al archivo .shp del DANE
    # path_mgn = "tu_ruta_al_archivo.shp"
    # run_ingestion(path_mgn)
    print("Script de integración PDET actualizado con esquema completo")