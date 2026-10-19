import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import type { AgentInfo } from "../api/client";
import { AgentDeck } from "./AgentDeck";

const agent = (id: string, name: string): AgentInfo => ({
  id,
  name,
  description: `${name} does one job.`,
  version: "0.1.0",
  primary_input: "target",
  uses_llm: false,
  input_schema: {},
  output_schema: {},
});

function renderDeck(agents: AgentInfo[]) {
  const router = createMemoryRouter([{ path: "/", element: <AgentDeck agents={agents} /> }]);
  return render(<RouterProvider router={router} />);
}

describe("AgentDeck", () => {
  it("shows one card per installed agent, at most four, the front one reachable", () => {
    renderDeck(["a", "b", "c", "d", "e"].map((id) => agent(id, `Agent ${id.toUpperCase()}`)));
    const links = screen.getAllByRole("link", { hidden: true });
    expect(links).toHaveLength(4);
    expect(screen.getAllByRole("link")).toHaveLength(1); // the cards behind are hidden from readers
    expect(screen.getByRole("link").getAttribute("href")).toBe("/agents/a");
  });

  it("brings another agent to the front from the pager", async () => {
    renderDeck([agent("a", "Agent A"), agent("b", "Agent B")]);
    await userEvent.setup().click(screen.getByRole("button", { name: "Show Agent B" }));
    expect(screen.getByRole("link").getAttribute("href")).toBe("/agents/b");
    expect(screen.getByText("2 / 2")).toBeTruthy();
  });

  it("shows no pager for a single agent", () => {
    renderDeck([agent("a", "Agent A")]);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
