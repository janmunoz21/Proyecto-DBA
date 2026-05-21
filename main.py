import sys
import load_pdet_municipalities as loader
import load_buildings as buildings_loader
import download_manager as dm


def show_menu() -> str:
    """Muestra el menú principal."""
    print("\n" + "="*60)
    print("MENU PRINCIPAL")
    print("="*60)
    print("\n1. Cargar datos en MongoDB")
    print("2. Verificar municipios PDET")
    print("3. Ingestar huellas de edificios - MICROSOF")
    print("4. Ingestar huellas de edificios - GOOGLE")
    print("5. Salir")
    
    while True:
        option = input("\nSelecciona una opcion (1-5): ").strip()
        if option in ['1', '2', '3', '4', '5']:
            return option
        print("Por favor, selecciona una opcion valida")


if __name__ == "__main__":
    try:
        # Verificar y descargar archivos necesarios
        if not dm.check_and_download_files(loader.SHP_PATH):
            print("\nNo se pudieron verificar/descargar todos los archivos necesarios")
            sys.exit(1)
        
        while True:
            option = show_menu()
            
            if option == '1':
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
            
            elif option == '2':
                mongo_uri = dm.get_mongodb_config()
                loader.MONGO_URI = mongo_uri
                loader.verify_pdet_municipalities()
            
            elif option == '3':
                # Flujo de descarga e ingesta de Microsoft
                target_file = dm.check_and_download_buildings("microsoft")
                if target_file:
                    mongo_uri = dm.get_mongodb_config()
                    buildings_loader.MONGO_URI = mongo_uri
                    if dm.ask_load_data():
                        buildings_loader.run_buildings_ingestion(target_file, "microsoft")
                else:
                    print(" Archivo de Microsoft no disponible para ejecucion\n")
                    
            elif option == '4':
                # Flujo de descarga e ingesta de Google
                target_file = dm.check_and_download_buildings("google")
                if target_file:
                    mongo_uri = dm.get_mongodb_config()
                    buildings_loader.MONGO_URI = mongo_uri
                    if dm.ask_load_data():
                        buildings_loader.run_buildings_ingestion(target_file, "google")
                else:
                    print(" Archivo de Google no disponible para ejecucion\n")
            
            elif option == '5':
                print("Saliendo del sistema\n")
                sys.exit(0)
    
    except KeyboardInterrupt:
        print("\n\nOperacion cancelada por el usuario\n")
        sys.exit(1)
    except Exception as e:
        print(f"\nError durante la ejecucion: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

