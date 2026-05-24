import os
import argparse
import requests
import zipfile
import time


# URLs de descarga
MGN_LINK  = "https://geoportal.dane.gov.co/descargas/mgn_2025/MGN2025_00_COLOMBIA.zip"
PDET_LINK = "https://centralpdet.renovacionterritorio.gov.co/wp-content/uploads/2022/01/MunicipiosPDET.xlsx"

# Microsoft: índice maestro con URLs particionadas por quadkey
# Referencia: https://github.com/microsoft/GlobalMLBuildingFootprints
MS_BUILDINGS_INDEX = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"
MS_BUILDINGS_DIR   = "ms_buildings"

# Google Open Buildings v3 — tiles S2 nivel 4 que cubren Colombia
# Acceso público directo desde Google Cloud Storage
# Referencia: https://sites.research.google/gr/open-buildings/
GOOGLE_BUILDINGS_BASE = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_4_gzip"
GOOGLE_BUILDINGS_TILES = ["177_buildings.csv.gz", "179_buildings.csv.gz", "17b_buildings.csv.gz"]
GOOGLE_BUILDINGS_DIR   = "google_buildings"

# Rutas de archivos
MGN_ZIP   = "MGN2025_00_COLOMBIA.zip"
PDET_FILE = "MunicipiosPDET.xlsx"


def file_exists(file_path: str) -> bool:
    """Verifica si un archivo existe."""
    return os.path.isfile(file_path)


def shapefile_exists(shp_path: str) -> bool:
    """Verifica si el shapefile existe."""
    return os.path.isfile(shp_path)


def download_file(url: str, filename: str) -> bool:
    """Descarga un archivo desde una URL con reintentos y reanudación parcial."""
    max_retries = 5
    chunk_size = 1024 * 1024  # 1MB para reducir overhead en archivos grandes

    for attempt in range(1, max_retries + 1):
        try:
            existing_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            headers = {}
            mode = "wb"

            if existing_size > 0:
                headers["Range"] = f"bytes={existing_size}-"
                mode = "ab"

            if existing_size > 0:
                print(f"Reintentando {filename} (intento {attempt}/{max_retries}) desde byte {existing_size:,}...")
            else:
                print(f"Descargando {filename} (intento {attempt}/{max_retries})...")

            with requests.get(url, stream=True, timeout=(15, 120), headers=headers) as response:
                if response.status_code == 416:
                    # El servidor reporta que ya no hay más bytes por descargar.
                    print(f"{filename} ya estaba descargado (respuesta 416).\n")
                    return True

                # Si el servidor no soporta Range, reiniciar desde cero.
                if existing_size > 0 and response.status_code == 200:
                    print("El servidor no soporta reanudación; reiniciando descarga desde cero...")
                    existing_size = 0
                    mode = "wb"

                response.raise_for_status()

                content_length = int(response.headers.get("content-length", 0))
                total_size = existing_size + content_length if content_length > 0 else 0
                downloaded = existing_size

                with open(filename, mode) as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percentage = (downloaded / total_size) * 100
                            print(f"Progreso: {percentage:.1f}%", end="\r")

                if total_size > 0 and downloaded < total_size:
                    raise IOError(
                        f"Descarga incompleta: {downloaded} de {total_size} bytes"
                    )

                print(f"\n{filename} descargado exitosamente\n")
                return True

        except Exception as e:
            print(f"Error al descargar {filename} (intento {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait_seconds = min(2 ** attempt, 10)
                print(f"Reintentando en {wait_seconds}s...\n")
                time.sleep(wait_seconds)
            else:
                print(f"Fallo definitivo al descargar {filename} tras {max_retries} intentos.\n")

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


def validate_zip(zip_path: str) -> bool:
    """Valida integridad básica del ZIP antes de extraer."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            bad_file = zip_ref.testzip()
            if bad_file is not None:
                print(f"ZIP corrupto: entrada inválida detectada ({bad_file})\n")
                return False
        return True
    except Exception as e:
        print(f"No se pudo validar el ZIP {zip_path}: {e}\n")
        return False


def check_and_download_files(shp_path: str, force_mgn_redownload: bool = False) -> bool:
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
    if force_mgn_redownload:
        print("   Redescarga forzada de MGN activada")
        if file_exists(MGN_ZIP):
            os.remove(MGN_ZIP)
            print(f"   Archivo previo eliminado: {MGN_ZIP}")
        part_file = f"{MGN_ZIP}.part"
        if file_exists(part_file):
            os.remove(part_file)
            print(f"   Archivo parcial eliminado: {part_file}")

    if shapefile_exists(shp_path) and not force_mgn_redownload:
        print(f"   Shapefile encontrado en {shp_path}\n")
    else:
        print(f"   Shapefile no encontrado")
        print("   Descargando datos MGN 2025...")
        if download_file(MGN_LINK, MGN_ZIP):
            if validate_zip(MGN_ZIP) and extract_zip(MGN_ZIP):
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



def _download_microsoft_buildings() -> str:
    """
    Descarga los 233 archivos particionados de Microsoft Buildings para Colombia
    usando el índice maestro. Devuelve la carpeta de destino si tiene éxito.
    """
    import io
    import csv

    os.makedirs(MS_BUILDINGS_DIR, exist_ok=True)

    print(f"Descargando índice maestro de Microsoft Buildings...")
    try:
        response = requests.get(MS_BUILDINGS_INDEX, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"Error al descargar el índice: {e}")
        return ""

    reader = csv.DictReader(io.StringIO(response.text))
    colombia_urls = [row["Url"] for row in reader if row.get("Location") == "Colombia"]

    if not colombia_urls:
        print("No se encontraron entradas de Colombia en el índice.")
        return ""

    print(f"Encontradas {len(colombia_urls)} particiones para Colombia.")
    total = len(colombia_urls)
    ok = 0
    for i, url in enumerate(colombia_urls, 1):
        filename = os.path.join(MS_BUILDINGS_DIR, url.split("/")[-1])
        if file_exists(filename):
            ok += 1
            print(f"  [{i}/{total}] Ya existe: {os.path.basename(filename)}")
            continue
        print(f"  [{i}/{total}] ", end="")
        if download_file(url, filename):
            ok += 1

    print(f"\nMicrosoft: {ok}/{total} particiones disponibles en '{MS_BUILDINGS_DIR}/'")
    return MS_BUILDINGS_DIR if ok > 0 else ""


def check_and_download_buildings(dataset_type: str) -> str:
    """
    Verifica y descarga los archivos de edificios de Microsoft o Google.
    Devuelve la ruta al archivo/carpeta listo para ingesta, o "" si no está disponible.
    """
    if dataset_type == "microsoft":
        print(f"\n-> Verificando dataset Microsoft Buildings en '{MS_BUILDINGS_DIR}/'")
        # Considerar disponible si la carpeta tiene al menos un archivo .csv.gz
        existing = []
        if os.path.isdir(MS_BUILDINGS_DIR):
            existing = [f for f in os.listdir(MS_BUILDINGS_DIR) if f.endswith(".csv.gz")]

        if existing:
            print(f"  {len(existing)} particiones ya descargadas en '{MS_BUILDINGS_DIR}/'.")
            return MS_BUILDINGS_DIR

        print("  Particiones no encontradas localmente.")
        confirm = input("¿Deseas descargar las 233 particiones de Colombia (~varios GB)? (s/n): ").strip().lower()
        if confirm == 's':
            return _download_microsoft_buildings()

        local_path = input("Ingresa la ruta a la carpeta con las particiones .csv.gz: ").strip()
        return local_path if os.path.isdir(local_path) else ""

    else:  # google
        print(f"\n-> Verificando dataset Google Open Buildings en '{GOOGLE_BUILDINGS_DIR}/'")
        os.makedirs(GOOGLE_BUILDINGS_DIR, exist_ok=True)

        existing = [f for f in os.listdir(GOOGLE_BUILDINGS_DIR) if f.endswith(".csv.gz")]
        if len(existing) == len(GOOGLE_BUILDINGS_TILES):
            print(f"  {len(existing)} tiles ya descargados en '{GOOGLE_BUILDINGS_DIR}/'.")
            return GOOGLE_BUILDINGS_DIR

        pending = [t for t in GOOGLE_BUILDINGS_TILES
                   if not file_exists(os.path.join(GOOGLE_BUILDINGS_DIR, t))]
        print(f"  {len(pending)} tiles pendientes de {len(GOOGLE_BUILDINGS_TILES)} (~3.5 GB total).")
        confirm = input("¿Deseas descargarlos ahora? (s/n): ").strip().lower()
        if confirm == 's':
            ok = 0
            for tile in pending:
                url  = f"{GOOGLE_BUILDINGS_BASE}/{tile}"
                dest = os.path.join(GOOGLE_BUILDINGS_DIR, tile)
                if download_file(url, dest):
                    ok += 1
            print(f"\nGoogle: {ok + (len(GOOGLE_BUILDINGS_TILES) - len(pending))}/{len(GOOGLE_BUILDINGS_TILES)} tiles disponibles.")
            return GOOGLE_BUILDINGS_DIR if ok > 0 else ""

        local_path = input("Ingresa la ruta a la carpeta con los tiles .csv.gz: ").strip()
        return local_path if os.path.isdir(local_path) else ""





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


def _run_cli() -> int:
    """Permite ejecutar este módulo directamente para verificar/descargar archivos base."""
    parser = argparse.ArgumentParser(
        description="Verifica y descarga MGN/PDET para el proyecto DBA"
    )
    parser.add_argument(
        "--shp-path",
        default="MGN_2025_COLOMBIA/ADMINISTRATIVO/MGN_ADM_MPIO_GRAFICO.shp",
        help="Ruta del shapefile municipal esperado"
    )
    parser.add_argument(
        "--force-mgn-redownload",
        action="store_true",
        help="Borra y descarga de nuevo el ZIP MGN antes de validar"
    )
    args = parser.parse_args()

    ok = check_and_download_files(
        shp_path=args.shp_path,
        force_mgn_redownload=args.force_mgn_redownload,
    )
    print(f"\nResultado final: {'OK' if ok else 'ERROR'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_run_cli())
