import { createBrowserRouter, Outlet, RouterProvider, ScrollRestoration } from "react-router";
import styles from "./App.module.css";
import { LinkButton } from "./components/Button";
import { NavRail } from "./components/NavRail";
import { EmptyState } from "./components/States";
import { AgentPage } from "./pages/AgentPage";
import { AgentsPage } from "./pages/AgentsPage";
import { HomePage } from "./pages/HomePage";
import { RunPage } from "./pages/RunPage";
import { RunsPage } from "./pages/RunsPage";

function Layout() {
  return (
    <div className={styles.shell}>
      <NavRail />
      <main className={styles.main}>
        <Outlet />
      </main>
      <ScrollRestoration />
    </div>
  );
}

function NotFound() {
  return (
    <EmptyState
      icon="explore_off"
      title="Nothing here"
      action={
        <LinkButton variant="tonal" to="/" icon="home">
          Home
        </LinkButton>
      }
    >
      <p>This page does not exist.</p>
    </EmptyState>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/agents", element: <AgentsPage /> },
      { path: "/agents/:agentId", element: <AgentPage /> },
      { path: "/runs", element: <RunsPage /> },
      { path: "/runs/:runId", element: <RunPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
