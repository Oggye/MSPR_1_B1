from sklearn.linear_model import Ridge

from .train_utils import (
    REG_CATEGORICAL_FEATURES,
    REG_NUMERIC_FEATURES,
    evaluate_regression,
    fit_production_model,
    load_regression_data,
    prepare_regression_data,
    save_model_and_metrics,
)


def train_ridge():
    print("\n--- Régression : Ridge ---")

    X, y = load_regression_data()
    prepared = prepare_regression_data(X, y)

    evaluation_model = Ridge(alpha=1.0)
    evaluation_model.fit(prepared.X_train, prepared.y_train)

    metrics = evaluate_regression(
        evaluation_model,
        prepared,
    )

    print("Métriques holdout temporel :")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")

    production_model, production_preprocessor = fit_production_model(
        evaluation_model,
        X,
        y,
        REG_NUMERIC_FEATURES,
        REG_CATEGORICAL_FEATURES,
    )

    save_model_and_metrics(
        production_model,
        metrics,
        "ridge",
        preprocessor=production_preprocessor,
        axis="reg",
    )


if __name__ == "__main__":
    train_ridge()
