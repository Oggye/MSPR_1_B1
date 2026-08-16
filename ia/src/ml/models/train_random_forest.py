from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from .train_utils import (
    CLF_CATEGORICAL_FEATURES,
    CLF_NUMERIC_FEATURES,
    REG_CATEGORICAL_FEATURES,
    REG_NUMERIC_FEATURES,
    evaluate_classification,
    evaluate_regression,
    fit_production_model,
    load_classification_data,
    load_regression_data,
    prepare_classification_data,
    prepare_regression_data,
    save_model_and_metrics,
)


def train_random_forest():
    print("\n--- Classification : Random Forest ---")

    X, y = load_classification_data()
    prepared = prepare_classification_data(X, y)

    evaluation_model = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    evaluation_model.fit(prepared.X_train, prepared.y_train)

    metrics = evaluate_classification(
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
        CLF_NUMERIC_FEATURES,
        CLF_CATEGORICAL_FEATURES,
    )

    save_model_and_metrics(
        production_model,
        metrics,
        "random_forest",
        preprocessor=production_preprocessor,
        axis="clf",
    )


def train_random_forest_regressor():
    print("\n--- Régression : Random Forest ---")

    X, y = load_regression_data()
    prepared = prepare_regression_data(X, y)

    evaluation_model = RandomForestRegressor(
        n_estimators=300,
        max_depth=10,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
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
        "random_forest",
        preprocessor=production_preprocessor,
        axis="reg",
    )


if __name__ == "__main__":
    train_random_forest()
    train_random_forest_regressor()
