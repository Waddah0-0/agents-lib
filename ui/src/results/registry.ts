/**
 * Custom result views, looked up by agent id. An agent without one gets the generic
 * viewer, which works for every AgentResult. The AI Code Detector's view is built in.
 */
import type { ComponentType } from "react";
import type { AgentResult, RunView } from "../api/client";
import { DetectorResult } from "./detector/DetectorResult";
import { GenericResult } from "./GenericResult";

export interface ResultViewProps {
  run: RunView;
  result: AgentResult;
}

// built-in custom views; more can be added with registerResultView
const views = new Map<string, ComponentType<ResultViewProps>>([["ai-code-detector", DetectorResult]]);

export function registerResultView(agentId: string, view: ComponentType<ResultViewProps>): void {
  views.set(agentId, view);
}

export function resultViewFor(agentId: string): ComponentType<ResultViewProps> {
  return views.get(agentId) ?? GenericResult;
}
