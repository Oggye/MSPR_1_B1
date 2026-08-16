import xgboost as xgb

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


def train_xgboost():
    print("\n--- Classification : XGBoost ---")

    X, y = load_classification_data()
    prepared = prepare_classification_data(X, y)

    n_neg = int((prepared.y_train == 0).sum())
    n_pos = int((prepared.y_train == 1).sum())
    scale = float(n_neg / n_pos) if n_pos > 0 else 1.0

    evaluation_model = xgb.XGBClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.85,
        colsample_bytree=0.9,
        random_state=42,
        eval_metric="logloss",
        scale_pos_weight=scale,
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
        "xgboost",
        preprocessor=production_preprocessor,
        axis="clf",
    )


def train_xgboost_regressor():
    print("\n--- Régression : XGBoost ---")

    X, y = load_regression_data()
    prepared = prepare_regression_data(X, y)

    evaluation_model = xgb.XGBRegressor(
        n_estimators=250,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.85,
        colsample_bytree=0.9,
        random_state=42,
        eval_metric="rmse",
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
        "xgboost",
        preprocessor=production_preprocessor,
        axis="reg",
    )


if __name__ == "__main__":
    train_xgboost()
    train_xgboost_regressor()
