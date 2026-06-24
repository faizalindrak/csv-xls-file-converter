from pathlib import Path
from shutil import rmtree

from file_converter import convert_to_xlsx


def test_convert_to_xlsx_preserves_non_finite_tokens_as_text():
    """CSV values such as NAN and INF should not crash XlsxWriter."""
    artifact_dir = Path("tests") / "_conversion_artifacts"
    source_path = artifact_dir / "non_finite.csv"
    output_path = artifact_dir / "non_finite.xlsx"
    artifact_dir.mkdir(exist_ok=True)

    try:
        source_path.write_text(
            "label,value\nalpha,NAN\nbeta,INF\ngamma,-INF\n",
            encoding="utf-8",
        )

        result = convert_to_xlsx(str(source_path), str(output_path))

        assert result == str(output_path)
        assert output_path.exists()
    finally:
        rmtree(artifact_dir, ignore_errors=True)
