import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "backend"))

from app.core.config import settings
from app.services.aws_document_processing import AwsDocumentProcessingService

JOBS = {
    "KVZBL2": "8c01658d06d5b9a0d1c20814cf95e0cfe2000ae0c74b246b934543651178c7a9",
    "KJPAZ9": "1baa87258eedb0140c3c1902c75e4e5e953141d46a62357aebf21c28d32bfc4f",
    "KNCADJ": "f057192c7a5ef19d63759faca555d34b6645292079bac252aeba8e1739055eed",
    "HVSTW5": "13a55b32990570022931c9b33cdc1b4e63fc1f7ebb101bed10f63fe76ba842e6",
}

service = AwsDocumentProcessingService(settings)
for name, job_id in JOBS.items():
    result = service.get_table_analysis(job_id)
    mapping = result.lesnina_mapping
    print("=" * 80)
    print(f"{name} | items={len(mapping.items)} | review={mapping.requires_review} | issues={mapping.issues}")
    for item in mapping.items:
        print(
            f"  {item.position} | {item.model_number}-{item.article_number} | qty={item.quantity} | "
            f"confidence={item.confidence:.1f}% | review={item.requires_review}"
        )
