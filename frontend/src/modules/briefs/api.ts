import { apiClient } from "@/api/request";

import type {
  BriefRevision,
  BriefRevisionUpdate,
  PreflightResult,
} from "./types";


interface BriefApiClient {
  get<T>(path: string, options?: { accessToken?: string }): Promise<T>;
  post<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string },
  ): Promise<T>;
  patch<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string },
  ): Promise<T>;
}

export function createBriefApi(client: BriefApiClient) {
  return {
    getBrief(briefId: string, accessToken: string) {
      return client.get<BriefRevision>(`/briefs/${briefId}`, { accessToken });
    },
    reviseBrief(
      briefId: string,
      update: BriefRevisionUpdate,
      accessToken: string,
    ) {
      return client.patch<BriefRevision>(`/briefs/${briefId}`, update, {
        accessToken,
      });
    },
    preflight(briefId: string, accessToken: string) {
      return client.post<PreflightResult>(
        "/generations/preflight",
        { brief_id: briefId },
        { accessToken },
      );
    },
    confirm(briefId: string, estimatedCredits: number, accessToken: string) {
      return client.post<PreflightResult>(
        `/briefs/${briefId}/confirm`,
        { accepted_estimated_credits: estimatedCredits },
        { accessToken },
      );
    },
  };
}

export const briefApi = createBriefApi(apiClient);
