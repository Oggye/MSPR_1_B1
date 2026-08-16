from .train_forecasting import main as train_forecasting


def main():
    print("=== Entraînement multi-horizon ObRail ===")
    train_forecasting()
    print("=== Entraînement multi-horizon terminé ===")


if __name__ == "__main__":
    main()
