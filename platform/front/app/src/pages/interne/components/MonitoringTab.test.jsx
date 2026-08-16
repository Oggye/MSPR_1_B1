import React from "react";
import { render, screen } from "@testing-library/react";

import MonitoringTab from "./MonitoringTab";

const monitoringData = {
  metrics: {},
  prometheus: { available: true, targets: [] },
  grafana: { dashboard_url: "http://localhost:3001/dashboard" },
};

test("affiche une supervision IA opérationnelle", () => {
  render(
    <MonitoringTab
      data={{
        ...monitoringData,
        ia: {
          available: true,
          status: "healthy",
          architecture: "direct_multi_horizon",
          version: 3,
          horizons: [1, 2, 3],
          artifacts: { manifest: true, classifier: true, regressor: true },
          classification: { model: "xgboost", overall: { f1: 0.82, roc_auc: 0.87 } },
          regression: { model: "xgboost", baseline: "persistence", overall: { mae: 123.4, r2: 0.75 } },
        },
      }}
    />
  );

  expect(screen.getByRole("heading", { name: "Supervision IA" })).toBeInTheDocument();
  expect(screen.getByText("Opérationnel")).toBeInTheDocument();
  expect(screen.getByText("N+1 · N+2 · N+3")).toBeInTheDocument();
});

test("reste lisible lorsque la supervision IA est absente", () => {
  render(<MonitoringTab data={monitoringData} />);

  expect(screen.getByRole("heading", { name: "Supervision IA" })).toBeInTheDocument();
  expect(screen.getAllByText("Indisponible").length).toBeGreaterThan(0);
  expect(screen.getByText("Les artefacts IA ne sont pas disponibles.")).toBeInTheDocument();
});
