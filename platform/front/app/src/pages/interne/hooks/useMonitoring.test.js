import { renderHook, waitFor } from "@testing-library/react";

import { useMonitoring } from "./useMonitoring";
import {
  getInternalOverview,
  runInternalDiagnostic,
} from "../../../services/api_interne";

jest.mock("../../../services/api_interne", () => ({
  getInternalOverview: jest.fn(),
  runInternalDiagnostic: jest.fn(),
  streamInternalTestsCategory: jest.fn(),
}));

test("lance une seule fois le diagnostic automatique lorsque le rapport est perime", async () => {
  getInternalOverview.mockResolvedValue({
    reports: {
      diagnostic: { date_diagnostic: "2026-01-01T00:00:00" },
      diagnostic_meta: { available: true, stale: true },
    },
  });
  runInternalDiagnostic.mockResolvedValue({
    success: true,
    report: { date_diagnostic: "2026-09-03T12:00:00" },
    report_meta: { available: true, stale: false },
  });

  const { rerender, unmount } = renderHook(() => useMonitoring(600000));

  await waitFor(() => expect(runInternalDiagnostic).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(getInternalOverview).toHaveBeenCalledTimes(2));
  rerender();
  expect(runInternalDiagnostic).toHaveBeenCalledTimes(1);

  unmount();
});
