"""
CLI entrypoint to seed the database from CSV (Point d'entrée CLI pour peupler la base de données depuis un fichier CSV).
Usage: python -m app.seed --csv data/Grid_view.csv (Utilisation : python -m app.seed --csv data/Grid_view.csv)
"""
import argparse
from app.core.config import get_today, DB_PATH
from app.services.seed_service import import_csv


def main() -> None:
    # Set up command line argument parsing (Configuration des arguments en ligne de commande)
    parser = argparse.ArgumentParser(
        description="Seed Smart CRM database from CSV (Peupler la base de données Smart CRM depuis un CSV)"
    )
    parser.add_argument("--csv", required=True, help="Path to CSV file (Chemin vers le fichier CSV)")
    parser.add_argument("--db", default=DB_PATH, help="Path to SQLite DB (Chemin vers la base SQLite)")
    args = parser.parse_args()

    print(f"\n[SEED] Seeding database: {args.db} (Initialisation de la base)")
    print(f"   CSV: {args.csv}")
    print(f"   Reference date / Date de référence: {get_today()}\n")

    # Run the import service (Exécution du service d'importation)
    report = import_csv(args.csv, args.db)

    print(f"[OK] Imported / Importés: {report['ok']} leads")
    print(f"[!]  Skipped / Ignorés:   {report['skipped']} rows")

    print("\n[STATS] Leads per rep (Leads par commercial):")
    for rep, count in sorted(report["rep_counts"].items()):
        print(f"   {rep}: {count}")

    print(f"\n[HOT] Hot leads with only 1 call / Leads chauds avec un seul appel: {report['hot_one_call']}")
    print("   --> Priority leads to follow up! (Leads prioritaires à relancer)")

    if report["skipped_reasons"]:
        print("\n[SKIP] Skipped rows details (Détails des lignes ignorées):")
        for reason in report["skipped_reasons"]:
            print(f"   {reason}")

    print("\n[DONE] Ready! Run: uvicorn app.main:app --reload (Prêt ! Lancez le serveur)\n")


if __name__ == "__main__":
    main()
