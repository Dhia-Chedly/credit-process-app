import { describe, expect, it } from "vitest";

import { apiPaths } from "./paths";

describe("public API paths", () => {
  it("builds the cutover resource and dashboard URLs", () => {
    expect(apiPaths.importBatches).toBe("/import-batches/");
    expect(apiPaths.assistantMessages).toBe("/assistant/messages/");
    expect(apiPaths.importBatch("batch/id")).toBe("/import-batches/batch%2Fid/");
    expect(apiPaths.importBatchIssues("batch-id")).toBe("/import-batches/batch-id/issues/");
    expect(apiPaths.importBatchRetry("batch-id")).toBe("/import-batches/batch-id/retry/");
    expect(apiPaths.creditRequests).toBe("/credit-requests/");
    expect(apiPaths.creditRequest("request/id")).toBe("/credit-requests/request%2Fid/");
    expect(apiPaths.dashboard("overview")).toBe("/dashboard/overview/");
    expect(apiPaths.me).toBe("/me/");
  });
});
