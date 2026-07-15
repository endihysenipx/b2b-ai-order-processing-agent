import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "backend"))

from app.core.config import settings
from app.services.aws_document_processing import AwsDocumentProcessingService

JOBS = {
    "KVZBL2": "8c01658d06d5b9a0d1c20814cf95e0cfe2000ae0c74b246b934543651178c7a9",
    "KJPAZ9": "1baa87258eedb0140c3c1902c75e4e5e953141d46a62357aebf21c28d32bfc4f",
    "HVSTW5": "13a55b32990570022931c9b33cdc1b4e63fc1f7ebb101bed10f63fe76ba842e6",
}

service = AwsDocumentProcessingService(settings)
for name, job_id in JOBS.items():
    result = service.get_table_analysis(job_id)
    print("=" * 100)
    print(name)
    for table_number, table in enumerate(result.tables, 1):
        print(f"TABLE {table_number} PAGE {table.page}")
        rows = {}
        for cell in table.cells:
            rows.setdefault(cell.row, {})[cell.column] = cell.text
        for row_number, row in sorted(rows.items()):
            values = " | ".join(f"c{column}={text}" for column, text in sorted(row.items()))
            print(f"r{row_number}: {values}")
