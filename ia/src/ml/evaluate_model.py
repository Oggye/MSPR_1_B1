import pandas as pd

from .config import REPORTS_DIR
from .models.train_utils import load_model_and_metrics


def load_all_metrics(axis="clf"):
    if axis == "clf":
        model_names = [
            "logistic",
            "random_forest",
            "xgboost",
            "mlp",
            "xgboost_optimized",
        ]
    else:
        model_names = [
            "ridge",
            "random_forest",
            "xgboost",
            "xgboost_optimized",
            "ridge_optimized",
        ]

    data = []
    for name in model_names:
        try:
            _, metrics = load_model_and_metrics(
                name,
                axis=axis,
            )
        except FileNotFoundError:
            continue

        row = dict(metrics)
        row["model"] = name
        data.append(row)

    return pd.DataFrame(data)


def save_comparison(df, filename, columns):
    if df.empty:
        print(f"Aucune métrique à comparer pour {filename}.")
        return

    selected = [column for column in columns if column in df.columns]
    output = df[selected].copy()

    path = REPORTS_DIR / filename
    output.to_csv(path, index=False)

    print(f"\nRapport : {path}")
    print(output.to_string(index=False))


def main():
    print("\nClassification — évaluation temporelle")
    clf = load_all_metrics("clf")
    save_comparison(
        clf,
        "comparison_classification.csv",
        [
            "model",
            "accuracy",
            "precision",
            "recall",
            "f1",
            "roc_auc",
            "baseline_accuracy",
            "baseline_f1",
            "train_year_min",
            "train_year_max",
            "test_year_min",
            "test_year_max",
        ],
    )

    print("\nRégression — évaluation temporelle")
    reg = load_all_metrics("reg")
    save_comparison(
        reg,
        "comparison_regression.csv",
        [
            "model",
            "mae",
            "rmse",
            "r2",
            "baseline_mae",
            "baseline_rmse",
            "baseline_r2",
            "beats_persistence_baseline_mae",
            "train_year_min",
            "train_year_max",
            "test_year_min",
            "test_year_max",
        ],
    )


if __name__ == "__main__":
    main()
