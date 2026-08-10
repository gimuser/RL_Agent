"""Dataset loading helpers."""

import pandas as pd


def load_train_data():
    path = "data/data_train.csv"
    return pd.read_csv(path)


def load_test_data():
    path = "data/data_test.csv"
    return pd.read_csv(path)


if __name__ == "__main__":

    train = load_train_data()
    test = load_test_data()

    print("Train shape :", train.shape)
    print("Test shape :", test.shape)

    print("\nTrain columns :")
    print(train.columns)

    print("\nPremieres lignes :")
    print(train.head())
