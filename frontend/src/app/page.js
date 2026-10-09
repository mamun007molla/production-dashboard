"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const initialJson = JSON.stringify(
  {
    source_id: "LINE-03",
    event_id: "EV-301",
    type: "COUNT",
    quantity: 5,
    target_event_id: null,
    event_time: new Date().toISOString(),
  },
  null,
  2,
);

const metrics = [
  { key: "net_total", label: "Net production", icon: "📦" },
  { key: "processed_events", label: "Processed events", icon: "✓" },
  { key: "pending_ack", label: "Pending ACK", icon: "◷" },
  { key: "unresolved", label: "Unresolved", icon: "⚠" },
  { key: "duplicates", label: "Duplicates", icon: "⧉" },
  { key: "conflicts", label: "Conflicts", icon: "⇄" },
  {
    key: "rejected_submissions",
    label: "Rejected submissions",
    icon: "⊘",
  },
];

export default function Home() {
  const [summary, setSummary] = useState(null);
  const [view, setView] = useState("summary");
  const [viewData, setViewData] = useState(null);
  const [jsonInput, setJsonInput] = useState(initialJson);
  const [sourceInput, setSourceInput] = useState("");
  const [appliedSource, setAppliedSource] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const buildStateUrl = useCallback(
    (selectedView) => {
      const params = new URLSearchParams({ view: selectedView });

      if (appliedSource.trim()) {
        params.set("source_id", appliedSource.trim());
      }

      return `${API_URL}/api/state?${params.toString()}`;
    },
    [appliedSource],
  );

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(buildStateUrl("summary"));

      if (!response.ok) {
        throw new Error(`Summary request failed (${response.status})`);
      }

      setSummary(await response.json());
    } catch (err) {
      setError(
        `${err.message}. Check that FastAPI is running and CORS is configured.`,
      );
    } finally {
      setLoading(false);
    }
  }, [buildStateUrl]);

  const loadView = useCallback(
    async (selectedView) => {
      setView(selectedView);
      setMessage("");
      setError("");

      if (selectedView === "summary") {
        setViewData(null);
        await loadSummary();
        return;
      }

      setViewData(null);

      try {
        const response = await fetch(buildStateUrl(selectedView));

        if (!response.ok) {
          throw new Error(`View request failed (${response.status})`);
        }

        setViewData(await response.json());
      } catch (err) {
        setError(err.message);
        setViewData(null);
      }
    },
    [buildStateUrl, loadSummary],
  );

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  async function applySourceFilter(event) {
    event.preventDefault();

    setAppliedSource(sourceInput.trim());
    setViewData(null);
    setMessage("");
    setError("");
  }

  async function clearSourceFilter() {
    setSourceInput("");
    setAppliedSource("");
    setViewData(null);
    setMessage("");
    setError("");
  }

  useEffect(() => {
    if (view !== "summary") {
      loadView(view);
    }
  }, [appliedSource, view, loadView]);

  async function submitEvents(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setMessage("");

    try {
      const payload = JSON.parse(jsonInput);

      const response = await fetch(`${API_URL}/api/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Request failed (${response.status})`);
      }

      setMessage(JSON.stringify(data, null, 2));

      await loadSummary();

      if (view !== "summary") {
        await loadView(view);
      }
    } catch (err) {
      setError(`Submission failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function acknowledge(eventId, sourceId) {
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        `${API_URL}/api/ack?source_id=${encodeURIComponent(sourceId)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ event_ids: [eventId] }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `ACK failed (${response.status})`);
      }

      setMessage(JSON.stringify(data, null, 2));

      await loadSummary();
      await loadView("pending");
    } catch (err) {
      setError(`Acknowledgement failed: ${err.message}`);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-5 py-8 md:px-8">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-400">
              NorthBridge Garments
            </p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight md:text-4xl">
              Production Dashboard
            </h1>
            <p className="mt-2 text-sm text-slate-400">
              Production events, exceptions and acknowledgements
            </p>
          </div>

          <button
            onClick={() => loadView(view)}
            disabled={loading}
            className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "↻ Refresh"}
          </button>
        </header>

        {error && (
          <div
            role="alert"
            className="mb-5 whitespace-pre-wrap rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200"
          >
            {error}
          </div>
        )}

        <section className="mb-6 rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <h2 className="text-lg font-semibold">Production source filter</h2>
          <p className="mt-1 text-sm text-slate-400">
            Enter a source ID to filter the dashboard, pending events and
            exceptions. Leave it empty to show all sources.
          </p>

          <form
            onSubmit={applySourceFilter}
            className="mt-4 flex flex-col gap-3 sm:flex-row"
          >
            <input
              type="text"
              value={sourceInput}
              onChange={(event) => setSourceInput(event.target.value)}
              placeholder="e.g. LINE-01"
              aria-label="Production source ID"
              className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none focus:border-cyan-500"
            />

            <button
              type="submit"
              className="rounded-xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-400"
            >
              Apply filter
            </button>

            <button
              type="button"
              onClick={clearSourceFilter}
              className="rounded-xl border border-slate-700 px-5 py-3 text-sm font-medium hover:bg-slate-800"
            >
              Clear
            </button>
          </form>

          <p className="mt-3 text-xs text-slate-400">
            Active source:{" "}
            <span className="font-semibold text-cyan-300">
              {appliedSource || "All sources"}
            </span>
          </p>
        </section>

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {metrics.map((metric) => (
            <article
              key={metric.key}
              className="rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-lg shadow-black/10"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-400">{metric.label}</p>
                <span className="text-xl" aria-hidden="true">
                  {metric.icon}
                </span>
              </div>

              <p className="mt-4 text-3xl font-bold tabular-nums">
                {summary ? (summary[metric.key] ?? 0) : "—"}
              </p>
            </article>
          ))}
        </section>

        <section className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <h2 className="text-lg font-semibold">Submit production events</h2>
            <p className="mt-1 text-sm text-slate-400">
              Submit one JSON object or an array of event objects.
            </p>

            <form onSubmit={submitEvents} className="mt-4">
              <label
                htmlFor="event-json"
                className="mb-2 block text-sm font-medium text-slate-300"
              >
                Event JSON
              </label>

              <textarea
                id="event-json"
                value={jsonInput}
                onChange={(event) => setJsonInput(event.target.value)}
                rows={13}
                spellCheck="false"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 p-4 font-mono text-sm leading-6 outline-none focus:border-cyan-500"
              />

              <button
                type="submit"
                disabled={submitting}
                className="mt-4 w-full rounded-xl bg-cyan-500 px-4 py-3 font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50"
              >
                {submitting ? "Submitting..." : "Submit event"}
              </button>
            </form>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <h2 className="text-lg font-semibold">Event operations</h2>
            <p className="mt-1 text-sm text-slate-400">
              Review pending acknowledgements and exceptions.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              {["summary", "pending", "exceptions"].map((item) => (
                <button
                  key={item}
                  onClick={() => loadView(item)}
                  className={`rounded-lg px-4 py-2 text-sm font-medium capitalize ${
                    view === item
                      ? "bg-cyan-500 text-slate-950"
                      : "border border-slate-700 text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>

            <div className="mt-5 space-y-3">
              {view === "summary" && (
                <p className="text-sm text-slate-400">
                  {appliedSource
                    ? `Summary filtered for ${appliedSource}.`
                    : "Showing summary for all production sources."}{" "}
                  Choose Pending or Exceptions to inspect event details.
                </p>
              )}

              {view === "pending" &&
                (viewData?.items?.length ? (
                  viewData.items.map((item) => (
                    <div
                      key={`${item.source_id}-${item.event_id}`}
                      className="rounded-xl border border-slate-800 p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold">{item.event_id}</p>
                          <p className="mt-1 text-xs text-slate-400">
                            {item.source_id} · {item.type} · {item.status}
                          </p>
                        </div>

                        <button
                          onClick={() =>
                            acknowledge(item.event_id, item.source_id)
                          }
                          className="rounded-lg bg-emerald-400 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300"
                        >
                          Acknowledge
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-400">
                    {viewData
                      ? "No pending events."
                      : "Loading pending events..."}
                  </p>
                ))}

              {view === "exceptions" && viewData && (
                <>
                  <ExceptionList
                    title="Unresolved events"
                    items={viewData.unresolved}
                  />
                  <ExceptionList
                    title="Duplicate submissions"
                    items={viewData.duplicates}
                  />
                  <ExceptionList
                    title="Conflicting submissions"
                    items={viewData.conflicts}
                  />
                </>
              )}

              {view === "exceptions" && !viewData && (
                <p className="text-sm text-slate-400">Loading exceptions...</p>
              )}
            </div>
          </div>
        </section>

        {(message || error) && (
          <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <h2 className="font-semibold">Latest response</h2>
            {message && (
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-sm text-emerald-300">
                {message}
              </pre>
            )}
          </section>
        )}

        <footer className="mt-10 border-t border-slate-800 pt-5 text-xs text-slate-500">
          Production Event Processing · FastAPI · PostgreSQL · MQTT
        </footer>
      </div>
    </main>
  );
}

function ExceptionList({ title, items = [] }) {
  return (
    <section className="rounded-xl border border-slate-800 p-4">
      <h3 className="font-medium">{title}</h3>

      {items.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">No items.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((item, index) => (
            <li
              key={`${item.source_id}-${item.event_id}-${index}`}
              className="rounded-lg bg-slate-950 p-3 text-sm"
            >
              <p className="font-medium">
                {item.source_id || "Unknown source"} /{" "}
                {item.event_id || "Unknown event"}
              </p>
              <p className="mt-1 break-words text-slate-400">
                {item.reason || item.status || "No details"}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
