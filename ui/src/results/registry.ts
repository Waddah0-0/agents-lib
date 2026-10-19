/**
 * Custom result views, looked up by agent id. An agent without one gets the generic
 * viewer, which works for every AgentResult. Phase 7 registers the detector's view here.
 */
import type { ComponentType } from "react";
import type { AgentResult, RunView } from "../api/client";
import { GenericResult } from "./GenericResult";

export interface ResultViewProps {
  run: RunView;
  result: AgentResult;
}

const views = new Map<string, ComponentType<ResultViewProps>>();

export function registerResultView(agentId: string, view: ComponentType<ResultViewProps>): void {
  views.set(agentId, view);
}

export function resultViewFor(agentId: string): ComponentType<ResultViewProps> {
  return views.get(agentId) ?? GenericResult;
}
