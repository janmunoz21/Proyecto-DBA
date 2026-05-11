import sys
import load_pdet_municipalities as loader
import download_manager as dm


if __name__ == "__main__":
    try:
        # Verificar y descargar archivos necesarios
        if not dm.check_and_download_files(loader.SHP_PATH):
            print("\nNo se pudieron verificar/descargar todos los archivos necesarios")
            sys.exit(1)
        
        # Obtener configuración de MongoDB
        mongo_uri = dm.get_mongodb_config()
        
        # Preguntar si cargar datos
        if dm.ask_load_data():
            loader.MONGO_URI = mongo_uri
            print("="*60)
            print("INICIANDO CARGA DE DATOS EN MONGODB")
            print("="*60 + "\n")
            loader.run_ingestion(loader.SHP_PATH)
        else:
            print("Operacion cancelada por el usuario\n")
    
    except KeyboardInterrupt:
        print("\n\nOperacion cancelada por el usuario\n")
        sys.exit(1)
    except Exception as e:
        print(f"\nError durante la ejecucion: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

