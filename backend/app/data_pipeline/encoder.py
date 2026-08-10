"""Data encoding helpers."""

from sklearn.preprocessing import LabelEncoder


def encode_data(train_df, test_df):

    columns_to_encode = [

        "Category",
        "MitreTechniques",
        "IncidentGrade",
        "ActionGrouped",
        "ActionGranular",
        "EntityType",
        "EvidenceRole",
        "ThreatFamily",
        "OSFamily",
        "SuspicionLevel",
        "LastVerdict"

    ]

    datasets = [train_df, test_df]

    for df in datasets:

        for col in columns_to_encode:

            encoder = LabelEncoder()

            df[col] = encoder.fit_transform(
                df[col].astype(str)
            )

    return train_df, test_df


if __name__ == "__main__":

    from loader import load_train_data, load_test_data
    from cleaner import clean_data
    from validator import validate_data

    train = clean_data(load_train_data())
    test = clean_data(load_test_data())

    validate_data(train, "TRAIN")
    validate_data(test, "TEST")

    train, test = encode_data(train, test)

    print(train.head())
    print(test.head())