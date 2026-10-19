import { type FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { type AgentInfo, ApiError, api, call } from "../api/client";
import { Button } from "../components/Button";
import { CopyButton } from "../components/CopyButton";
import { Icon } from "../components/Icon";
import { FieldInput } from "./Fields";
import styles from "./SchemaForm.module.css";
import {
  buildPayload,
  cliCommand,
  type FormValue,
  type FormValues,
  fieldsFromSchema,
  initialValues,
} from "./schema";

export async function startRun(agentId: string, payload: Record<string, unknown>): Promise<string> {
  const created = await call(
    api.POST("/agents/{agent_id}/runs", { params: { path: { agent_id: agentId } }, body: payload }),
  );
  return created.run_id;
}

/** The input form for any agent, generated from its JSON schema. */
export function SchemaForm({ agent, initial }: { agent: AgentInfo; initial?: FormValues }) {
  const navigate = useNavigate();
  const fields = useMemo(() => fieldsFromSchema(agent.input_schema, agent.primary_input), [agent]);
  const [values, setValues] = useState<FormValues>(() => ({ ...initialValues(fields), ...initial }));
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string>();

  const { payload, errors } = buildPayload(fields, values);
  const shownErrors = touched ? errors : {};
  const main = fields.filter((f) => f.primary || f.required);
  const extra = fields.filter((f) => !f.primary && !f.required);
  const changedExtra = extra.filter((f) => f.name in payload).length;

  const set = (name: string) => (value: FormValue) => {
    setValues((v) => ({ ...v, [name]: value }));
    setServerError(undefined);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (Object.keys(errors).length) return;
    setSubmitting(true);
    setServerError(undefined);
    try {
      const runId = await startRun(agent.id, payload);
      navigate(`/runs/${runId}`, { viewTransition: true });
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : (err as Error).message);
      setSubmitting(false);
    }
  };

  const reset = () => {
    setValues(initialValues(fields));
    setTouched(false);
    setServerError(undefined);
  };

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <div className={styles.fields}>
        {main.map((field, i) => (
          <FieldInput
            key={field.name}
            field={field}
            value={values[field.name] ?? null}
            error={shownErrors[field.name]}
            onChange={set(field.name)}
            autoFocus={i === 0}
          />
        ))}
      </div>

      {extra.length > 0 && (
        <details className={styles.more} open={changedExtra > 0 || undefined}>
          <summary className={styles.summary}>
            <Icon name="options" />
            <span>More options</span>
            <span className={styles.count}>
              {changedExtra ? `${changedExtra} changed` : `${extra.length}`}
            </span>
            <Icon name="expand" className={styles.chevron} />
          </summary>
          <div className={styles.fields}>
            {extra.map((field) => (
              <FieldInput
                key={field.name}
                field={field}
                value={values[field.name] ?? null}
                error={shownErrors[field.name]}
                onChange={set(field.name)}
              />
            ))}
          </div>
        </details>
      )}

      {serverError && (
        <div className={styles.error} role="alert">
          <Icon name="error" />
          <span>{serverError}</span>
        </div>
      )}

      <div className={styles.actions}>
        <Button type="submit" size="l" icon={submitting ? "spinner" : "play"} disabled={submitting}>
          {submitting ? "Starting" : "Run"}
        </Button>
        <Button variant="text" onClick={reset} disabled={submitting}>
          Reset
        </Button>
      </div>

      <div className={styles.cli}>
        <div className={styles.cliHead}>
          <span className="label-m muted">Same run from the command line</span>
          <CopyButton text={cliCommand(agent.id, fields, payload)} label="Copy command" />
        </div>
        <code className={styles.cliCode}>{cliCommand(agent.id, fields, payload)}</code>
      </div>
    </form>
  );
}
