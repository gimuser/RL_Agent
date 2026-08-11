"""Tests for the processed dataset contract and feature schema."""

from app.data_pipeline.contract import FEATURE_COLUMNS, REQUIRED_PROCESSED_COLUMNS, audit_processed_split, load_processed_split


def test_train_and_test_splits_have_expected_schema():
    train = load_processed_split("train")
    test = load_processed_split("test")
    assert len(train.columns) == len(REQUIRED_PROCESSED_COLUMNS)
    assert len(test.columns) == len(REQUIRED_PROCESSED_COLUMNS)
    assert list(FEATURE_COLUMNS) == [
        "Category",
        "MitreTechniques",
        "EntityType",
        "EvidenceRole",
        "ThreatFamily",
        "OSFamily",
        "SuspicionLevel",
        "hour",
        "day",
        "month",
        "is_weekend",
    ]
    assert audit_processed_split("train").rows > 0
    assert audit_processed_split("test").rows > 0
