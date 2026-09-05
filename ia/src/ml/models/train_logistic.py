from sklearn.linear_model import LogisticRegression

from .train_utils import (
    CLF_CATEGORICAL_FEATURES,
    CLF_NUMERIC_FEATURES,
    evaluate_classification,
    fit_production_model,
    load_classification_data,
    prepare_classification_data,
    save_model_and_metrics,
)


def train_logistic():
    print("\n--- Classification : Logistic Regression ---")

    X, y = load_classification_data()
    prepared = prepare_classification_data(X, y)

    evaluation_model = LogisticRegression(
        max_iter=2000,
        random_state=42,
        class_weight="balanced",
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
        "logistic",
        preprocessor=production_preprocessor,
        axis="clf",
    )


if __name__ == "__main__":
    train_logistic()
