import os
import requests
import zipfile


# URLs de descarga
MGN_LINK = "https://geoportal.dane.gov.co/descargas/mgn_2025/MGN2025_00_COLOMBIA.zip"
PDET_LINK = "https://centralpdet.renovacionterritorio.gov.co/wp-content/uploads/2022/01/MunicipiosPDET.xlsx"

# Urls de edificios - TODO: verificar los links porque no estoy segura si están del todo bien
MICROSOFT_BUILDINGS_LINK = "https://minedbuildings.blob.core.windows.net/colombia/Colombia.geojson"
GOOGLE_BUILDINGS_LINK = "https://data.sourcecoop.io/google-open-buildings/v3/colombia.geojson"

# mi opción B son estos links:
# https://github.com/microsoft/GlobalMLBuildingFootprints
# https://sites.research.google/open-buildings/?hl=es-419
# https://sites.research.google/gr/open-buildings/

# Rutas de archivos
MGN_ZIP = "MGN2025_00_COLOMBIA.zip"
PDET_FILE = "MunicipiosPDET.xlsx"
MS_BUILDINGS_FILE = "buildings_microsoft.geojson"
GOOG_BUILDINGS_FILE = "buildings_google.geojson"


def file_exists(file_path: str) -> bool:
    """Verifica si un archivo existe."""
    return os.path.isfile(file_path)


def shapefile_exists(shp_path: str) -> bool:
    """Verifica si el shapefile existe."""
    return os.path.isfile(shp_path)


def download_file(url: str, filename: str) -> bool:
    """Descarga un archivo desde una URL."""
    try:
        print(f"Descargando {filename}...")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percentage = (downloaded / total_size) * 100
                        print(f"Progreso: {percentage:.1f}%", end='\r')
        
        print(f"{filename} descargado exitosamente\n")
        return True
    except Exception as e:
        print(f"Error al descargar {filename}: {e}\n")
        return False


def extract_zip(zip_path: str, extract_path: str = ".") -> bool:
    """Extrae un archivo ZIP."""
    try:
        print(f"Extrayendo {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        print(f"{zip_path} extraído exitosamente\n")
        return True
    except Exception as e:
        print(f"Error al extraer {zip_path}: {e}\n")
        return False


def check_and_download_files(shp_path: str) -> bool:
    """Verifica la existencia de archivos necesarios y los descarga si es necesario."""
    print("\n" + "="*60)
    print("VERIFICACION DE ARCHIVOS")
    print("="*60 + "\n")
    
    files_ok = True
    
    # Verificar Excel PDET
    print(f"1. Verificando {PDET_FILE}...")
    if file_exists(PDET_FILE):
        print(f"   {PDET_FILE} encontrado\n")
    else:
        print(f"   {PDET_FILE} no encontrado")
        if download_file(PDET_LINK, PDET_FILE):
            print(f"   {PDET_FILE} listo para usar\n")
        else:
            files_ok = False
    
    # Verificar shapefile
    print(f"2. Verificando shapefile...")
    if shapefile_exists(shp_path):
        print(f"   Shapefile encontrado en {shp_path}\n")
    else:
        print(f"   Shapefile no encontrado")
        print("   Descargando datos MGN 2025...")
        if download_file(MGN_LINK, MGN_ZIP):
            if extract_zip(MGN_ZIP):
                if shapefile_exists(shp_path):
                    print(f"   Shapefile listo para usar\n")
                else:
                    print(f"   No se encontro el shapefile despues de la extraccion\n")
                    files_ok = False
            else:
                files_ok = False
        else:
            files_ok = False
    
    return files_ok



def check_and_download_buildings(dataset_type: str) -> str:
    """Verifica y descarga específicamente los archivos de edificios de Microsoft o Google"""
    if dataset_type == "microsoft":
        url = MICROSOFT_BUILDINGS_LINK
        filename = MS_BUILDINGS_FILE
    else:
        url = GOOGLE_BUILDINGS_LINK
        filename = GOOG_BUILDINGS_FILE
        
    print(f"\n-> Verificando fuente de edificios: {filename}")
    if file_exists(filename):
        print(f"✓ Dataset de {dataset_type} ya se encuentra en el directorio local.")
        return filename
        
    print(f"⚠ Dataset de {dataset_type} faltante.")
    # Nota: los archivos pesan gigabytes en entornos reales
    # Es por esto que se deja el flujo listo para descargar o mapear localmente de forma segura
    confirm = input(f"¿Deseas intentar descargar el archivo remoto de {dataset_type}? (s/n): ").strip().lower()
    if confirm == 's':
        if download_file(url, filename):
            return filename
    
    # Si no se descarga, se solicita la ruta local
    local_path = input(f"Por favor ingresa la ruta local de tu archivo {dataset_type} (ej: data/{filename}): ").strip()
    return local_path if file_exists(local_path) else ""





def get_mongodb_config() -> str:
    """Solicita la configuración de MongoDB."""
    print("="*60)
    print("CONFIGURACION DE MONGODB")
    print("="*60 + "\n")
    
    mongo_ip = input("Ingresa la IP de MongoDB (deja en blanco para localhost): ").strip()
    
    if mongo_ip == "":
        mongo_uri = "mongodb://localhost:27017/"
        print(f"Usando MongoDB local: {mongo_uri}\n")
    else:
        mongo_uri = f"mongodb://{mongo_ip}:27017/"
        print(f"Usando MongoDB en: {mongo_uri}\n")
    
    return mongo_uri


def ask_load_data() -> bool:
    """Pregunta si se deben cargar los datos en MongoDB."""
    print("="*60)
    print("OPCIONES DE CARGA DE DATOS")
    print("="*60 + "\n")
    
    while True:
        response = input("Deseas cargar los datos en MongoDB? (s/n): ").strip().lower()
        if response in ['s', 'si', 'sí', 'y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Por favor, responde 's' o 'n'")
