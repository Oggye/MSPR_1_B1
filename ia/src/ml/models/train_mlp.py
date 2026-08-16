from sklearn.neural_network import MLPClassifier

from .train_utils import (
    CLF_CATEGORICAL_FEATURES,
    CLF_NUMERIC_FEATURES,
    evaluate_classification,
    fit_production_model,
    load_classification_data,
    prepare_classification_data,
    save_model_and_metrics,
)


def train_mlp():
    print("\n--- Classification : MLP ---")

    X, y = load_classification_data()
    prepared = prepare_classification_data(X, y)

    evaluation_model = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        alpha=0.001,
        max_iter=1500,
        early_stopping=True,
        validation_fraction=0.15,
        random_state=42,
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
        "mlp",
        preprocessor=production_preprocessor,
        axis="clf",
    )


if __name__ == "__main__":
    train_mlp()
