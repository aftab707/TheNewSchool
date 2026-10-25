"""tests/test_seed.py — Tests for the CSV import and mock-data generation."""
import os
import tempfile
import csv
import pytest

os.environ.setdefault("CRM_TODAY", "2026-07-20")


@pytest.fixture
def sample_csv(tmp_path):
    """Create a minimal valid CSV file with UTF-8 BOM."""
    path = tmp_path / "test.csv"
    content = (
        "\ufeffMail,Nom,Prénom,Commercial,Chaleur,Date d'arrivée,Nombre d'appel\n"
        "alice@example.com,Martin,Alice,Guillaume,8,4/21/2026,1\n"
        "chloé.bernard@example.com,Bernard,Chloé,Adrien,5,5/01/2026,2\n"
        "bob@example.com,Dupont,Bob,Antoine,0,6/15/2026,3\n"
    )
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def bad_csv(tmp_path):
    """CSV with an invalid row."""
    path = tmp_path / "bad.csv"
    content = (
        "Mail,Nom,Prénom,Commercial,Chaleur,Date d'arrivée,Nombre d'appel\n"
        "valid@example.com,Test,User,Guillaume,5,4/21/2026,1\n"
        "not-an-email,Bad,Row,Adrien,5,4/21/2026,1\n"
    )
    path.write_text(content, encoding="utf-8")
    return str(path)


class TestSeedImport:
    def test_bom_handled(self, sample_csv, tmp_path):
        """Should import 3 rows despite UTF-8 BOM."""
        from app.services.seed_service import import_csv
        db = str(tmp_path / "test.db")
        report = import_csv(sample_csv, db_path=db)
        assert report["ok"] == 3
        assert report["skipped"] == 0

    def test_accents_preserved(self, sample_csv, tmp_path):
        """Email with accents should be stored as-is."""
        from app.services.seed_service import import_csv
        from app.repositories.lead_repository import get_lead_by_email
        db = str(tmp_path / "test.db")
        import_csv(sample_csv, db_path=db)
        lead = get_lead_by_email("chloé.bernard@example.com", db_path=db)
        assert lead is not None
        assert lead["email"] == "chloé.bernard@example.com"

    def test_100_rows_imported(self, tmp_path):
        """Full CSV should produce exactly 100 leads."""
        from app.services.seed_service import import_csv
        db = str(tmp_path / "full.db")
        csv_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "Grid_view.csv"
        )
        if not os.path.exists(csv_path):
            pytest.skip("Grid_view.csv not found")
        report = import_csv(csv_path, db_path=db)
        assert report["ok"] == 100
        assert report["skipped"] == 0

    def test_idempotent_reimport(self, sample_csv, tmp_path):
        """Re-running import should not duplicate leads."""
        from app.services.seed_service import import_csv
        from app.repositories.lead_repository import list_leads
        db = str(tmp_path / "idem.db")
        import_csv(sample_csv, db_path=db)
        import_csv(sample_csv, db_path=db)
        leads = list_leads(db_path=db)
        assert len(leads) == 3

    def test_invalid_row_reported(self, bad_csv, tmp_path):
        """Invalid email row should be skipped with a reason."""
        from app.services.seed_service import import_csv
        db = str(tmp_path / "bad.db")
        report = import_csv(bad_csv, db_path=db)
        assert report["ok"] == 1
        assert report["skipped"] == 1
        assert len(report["skipped_reasons"]) == 1

    def test_hot_one_call_count(self, tmp_path):
        """Should correctly count hot leads (chaleur>=7) with only 1 call."""
        from app.services.seed_service import import_csv
        db = str(tmp_path / "hot.db")
        csv_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "Grid_view.csv"
        )
        if not os.path.exists(csv_path):
            pytest.skip("Grid_view.csv not found")
        report = import_csv(csv_path, db_path=db)
        # At least some hot leads with 1 call should be found
        assert report["hot_one_call"] >= 1
