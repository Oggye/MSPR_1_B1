import React from "react";
import { render, screen } from "@testing-library/react";

import MonitoringTab from "./MonitoringTab";

const monitoringData = {
  metrics: {},
  prometheus: { available: true, targets: [] },
  grafana: {
    dashboard_url: "http://localhost:3001/dashboard",
    ia_dashboard_url: "http://localhost:3001/d/obrail-ia-monitoring/obrail-ia-monitoring",
  },
};

const offlineIa = {
  available: true,
  status: "healthy",
  architecture: "direct_multi_horizon",
  version: 3,
  horizons: [1, 2, 3],
  artifacts: { manifest: true, classifier: true, regressor: true },
  classification: {
    model: "xgboost",
    overall: { f1: 0.82, roc_auc: 0.87, accuracy: 0.8 },
  },
  regression: {
    model: "xgboost",
    baseline: "persistence",
    overall: { mae: 123.4, rmse: 160.2, r2: 0.75 },
  },
};

test("affiche les métriques runtime et conserve la supervision offline", () => {
  render(
    <MonitoringTab
      data={{
        ...monitoringData,
        ia: {
          ...offlineIa,
          runtime: {
            available: true,
            status: "healthy",
            predictions_success: 12,
            predictions_error: 0,
            latency_p95_seconds: 0.084,
            classification: {
              total: 7,
              distribution: {
                "Croissance / stabilité probable": 4,
                "Baisse probable": 3,
              },
            },
            regression: {
              total: 5,
              distribution: { Croissance: 3, Stable: 1, Déclin: 1 },
            },
          },
        },
      }}
    />
  );

  expect(screen.getByRole("heading", { name: "Supervision IA" })).toBeInTheDocument();
  expect(screen.getByText("Opérationnel")).toBeInTheDocument();
  expect(screen.getByText("N+1 · N+2 · N+3")).toBeInTheDocument();
  expect(screen.getByRole("heading",{ name: "Modèles déployés et test final" })).toBeInTheDocument();
  expect(screen.getByRole("heading",{ name: "Sélection des modèles de production" })).toBeInTheDocument();
  expect(screen.getByRole("heading",{ name: "Benchmark historique N+1" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Activité IA en fonctionnement" })).toBeInTheDocument();
  expect(screen.getByText("Prédictions réussies")).toBeInTheDocument();
  expect(screen.getByText("Erreurs d’inférence")).toBeInTheDocument();
  expect(screen.getAllByText("Latence P95").length).toBeGreaterThan(0);
  expect(screen.getByText("Croissance / stabilité probable")).toBeInTheDocument();
  expect(screen.getByText("Baisse probable")).toBeInTheDocument();
  expect(screen.getAllByText(/F1/).length).toBeGreaterThan(0);
  expect(screen.getByText("ROC-AUC")).toBeInTheDocument();
  expect(screen.getAllByText(/MAE/).length).toBeGreaterThan(0);
  expect(screen.getByText("R²")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Artefacts" })).toBeInTheDocument();
});

test("conserve les données offline lorsque le runtime est indisponible", () => {
  render(
    <MonitoringTab
      data={{
        ...monitoringData,
        ia: {
          ...offlineIa,
          runtime: { available: false, status: "unavailable" },
        },
      }}
    />
  );

  expect(screen.getByRole("heading", { name: "Supervision IA" })).toBeInTheDocument();
  expect(screen.getByText("Données runtime indisponibles. La supervision du modèle déployé reste accessible.")).toBeInTheDocument();
  expect(screen.getByText("F1")).toBeInTheDocument();
  expect(screen.getByText("MAE")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Artefacts" })).toBeInTheDocument();
});

test("explique normalement l’absence de première prédiction", () => {
  render(
    <MonitoringTab
      data={{
        ...monitoringData,
        ia: {
          ...offlineIa,
          runtime: {
            available: true,
            status: "no_data",
            predictions_success: 0,
            predictions_error: 0,
            latency_p95_seconds: null,
            classification: { total: 0, distribution: {} },
            regression: { total: 0, distribution: {} },
          },
        },
      }}
    />
  );

  expect(screen.getAllByText("Aucune donnée").length).toBeGreaterThan(0);
  expect(screen.getByText(/Aucune activité IA observée depuis le démarrage/)).toBeInTheDocument();
  expect(screen.getAllByText("N/A").length).toBeGreaterThan(0);
});
