import { request } from "../api-client";

export interface ImportAllResult {
  created: number;
  updated: number;
  skipped: number;
  errors: { kind?: string; id?: string; message: string }[];
  warnings: { kind?: string; id?: string; message: string }[];
}

export async function importAllDefinitions(definitions: unknown[]): Promise<ImportAllResult> {
  return request<ImportAllResult>("/api/definitions/import-all", {
    method: "POST",
    body: JSON.stringify({ definitions }),
  });
}
