"""Normalization helpers."""

import pandas as pd
from sklearn.preprocessing import MinMaxScaler


def normalize_data(train_df, test_df):

    columns = [

        "IncidentId",
        "hour",
        "day",
        "month",
        "is_weekend"

    ]

    # نجمعو train و test

    full_df = pd.concat(
        [train_df, test_df],
        ignore_index=True
    )

    # Normalization

    scaler = MinMaxScaler()

    full_df[columns] = scaler.fit_transform(
        full_df[columns]
    )

    # نرجعو نقسموهم

    train_size = len(train_df)

    train_df = full_df.iloc[:train_size].reset_index(
        drop=True
    )

    test_df = full_df.iloc[train_size:].reset_index(
        drop=True
    )

    return train_df, test_df


if __name__ == "__main__":

    from loader import load_train_data
    from loader import load_test_data

    from cleaner import clean_data

    from validator import validate_data

    from encoder import encode_data

    from feature_engineering import create_features

    train = load_train_data()
    test = load_test_data()

    train = clean_data(train)
    test = clean_data(test)

    validate_data(train, "TRAIN")
    validate_data(test, "TEST")

    train, test = encode_data(train, test)

    train, test = create_features(train, test)

    train, test = normalize_data(
        train,
        test
    )

    print("\n=== TRAIN ===")

    print(
        train[
            [
                "IncidentId",
                "hour",
                "day",
                "month",
                "is_weekend"
            ]
        ].head()
    )

    print("\n=== TEST ===")

    print(
        test[
            [
                "IncidentId",
                "hour",
                "day",
                "month",
                "is_weekend"
            ]
        ].head()
    )