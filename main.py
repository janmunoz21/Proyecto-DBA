import sys
import load_pdet_municipalities as loader
import load_buildings as buildings_loader
import download_manager as dm
import eda_buildings as eda


def show_menu() -> str:
    """Muestra el menú principal."""
    print("\n" + "="*60)
    print("MENU PRINCIPAL")
    print("="*60)
    print("1. Cargar municipios PDET en MongoDB")
    print("2. Verificar municipios PDET")
    print("3. Ingestar huellas de edificios - MICROSOFT")
    print("4. Ingestar huellas de edificios - GOOGLE")
    print("5. Reparar y reindexar colecciones de edificios")
    print("6. Análisis geoespacial (conteo y área por municipio)")
    print("7. EDA - Auditoría exploratoria completa")
    print("\n8. Salir")

    while True:
        option = input("\nSelecciona una opcion (1-8): ").strip()
        if option in ['1', '2', '3', '4', '5', '6', '7', '8']:
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

            try:
                if option == '1':
                    mongo_uri = dm.get_mongodb_config()
                    if dm.ask_load_data():
                        loader.MONGO_URI = mongo_uri
                        print("="*60)
                        print("INICIANDO CARGA DE MUNICIPIOS PDET EN MONGODB")
                        print("="*60 + "\n")
                        loader.run_ingestion(loader.SHP_PATH)
                    else:
                        print("Operacion cancelada por el usuario\n")

                elif option == '2':
                    mongo_uri = dm.get_mongodb_config()
                    loader.MONGO_URI = mongo_uri
                    loader.verify_pdet_municipalities()

                elif option == '3':
                    target_file = dm.check_and_download_buildings("microsoft")
                    if target_file:
                        mongo_uri = dm.get_mongodb_config()
                        buildings_loader.MONGO_URI = mongo_uri
                        if dm.ask_load_data():
                            buildings_loader.run_buildings_ingestion(target_file, "microsoft")
                    else:
                        print(" Archivo de Microsoft no disponible para ejecucion\n")

                elif option == '4':
                    target_file = dm.check_and_download_buildings("google")
                    if target_file:
                        mongo_uri = dm.get_mongodb_config()
                        buildings_loader.MONGO_URI = mongo_uri
                        if dm.ask_load_data():
                            buildings_loader.run_buildings_ingestion(target_file, "google")
                    else:
                        print(" Archivo de Google no disponible para ejecucion\n")

                elif option == '5':
                    mongo_uri = dm.get_mongodb_config()
                    buildings_loader.MONGO_URI = mongo_uri
                    buildings_loader.run_repair_and_reindex()

                elif option == '6':
                    mongo_uri = dm.get_mongodb_config()
                    eda.MONGO_URI = mongo_uri
                    eda.run_spatial_analysis_standalone()

                elif option == '7':
                    mongo_uri = dm.get_mongodb_config()
                    eda.MONGO_URI = mongo_uri
                    eda.run_eda()

                elif option == '8':
                    print("Saliendo del sistema\n")
                    sys.exit(0)

            except RuntimeError as e:
                print(f"\nError: {e}\n")
            except Exception as e:
                print(f"\nError durante la ejecucion: {e}\n")
                import traceback
                traceback.print_exc()
    
    except KeyboardInterrupt:
        print("\n\nOperacion cancelada por el usuario\n")
        sys.exit(1)
    except Exception as e:
        print(f"\nError durante la ejecucion: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

