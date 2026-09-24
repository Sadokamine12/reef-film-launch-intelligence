from training_engine import run_all_training, generate_active_learning_plan


def main():
    print("REEF Resolution ML trainer — professional Windows-safe edition")
    print("Backend: numpy/pandas bootstrap ridge ensemble + empirical PAVA baseline")
    print("=" * 78)
    results = run_all_training()
    for r in results:
        print(f"\n{r.name}: {r.status.upper()}")
        print(f"  rows: {r.rows}")
        if r.target:
            print(f"  target: {r.target}")
        if r.validation_mode:
            print(f"  validation: {r.validation_mode}")
        if r.mae is not None:
            print(f"  CV MAE: {r.mae:.3f}")
        if r.r2 is not None:
            print(f"  CV R2: {r.r2:.3f}")
        if r.benchmark_mae is not None:
            print(f"  empirical benchmark MAE: {r.benchmark_mae:.3f}")
        print(f"  operational: {'YES' if r.operational else 'NO'}")
        if r.model_path:
            print(f"  saved: {r.model_path}")
        print(f"  {r.notes}")
    plan = generate_active_learning_plan()
    print("\nExperiment plan")
    print(f"  planned learning spend: EUR {plan['planned_spend_eur'].sum():.2f}")
    print("  saved: data/experiment_plan.csv")
    print("\nStatus saved: data/training_status.json")


if __name__ == "__main__":
    main()
