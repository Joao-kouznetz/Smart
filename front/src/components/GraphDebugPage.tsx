import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import { ApiError, fetchLocationGraph, rebuildLocationGraph } from "../lib/api";
import type { LocationGraphLink, LocationGraphNode, LocationGraphPayload } from "../lib/types";

function getNodeId(value: string | LocationGraphNode): string {
  return typeof value === "string" ? value : value.id;
}

function formatSeconds(value: number | null | undefined): string {
  if (value == null) return "-";
  if (value < 60) return `${value.toFixed(1)}s`;
  return `${(value / 60).toFixed(1)}min`;
}

function nodeLabel(node: LocationGraphNode): string {
  return `${node.name}\nBarcode ${node.barcode}${node.aisle ? `\nCorredor ${node.aisle}` : ""}`;
}

function linkLabel(link: LocationGraphLink): string {
  return [
    `${getNodeId(link.source)} -> ${getNodeId(link.target)}`,
    `Tempo medio: ${formatSeconds(link.avg_elapsed_seconds)}`,
    `Transicoes: ${link.transition_count}`,
  ].join("\n");
}

export function GraphDebugPage() {
  const graphRef = useRef<any>(null);
  const [graph, setGraph] = useState<LocationGraphPayload | null>(null);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [startAt, setStartAt] = useState("");
  const [temporalDecay, setTemporalDecay] = useState(false);
  const [halfLifeDays, setHalfLifeDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<"info" | "error" | "success">("info");

  async function loadGraph() {
    setLoading(true);
    setMessage(null);
    try {
      const payload = await fetchLocationGraph();
      setGraph(payload);
    } catch (error) {
      const detail =
        error instanceof ApiError
          ? error.message
          : "Nao foi possivel carregar o grafo de localizacao.";
      setGraph(null);
      setMessageTone("error");
      setMessage(detail);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadGraph();
  }, []);

  useEffect(() => {
    if (!graph || !graphRef.current) return;
    const linkForce = graphRef.current.d3Force("link");
    if (linkForce) {
      linkForce.distance((link: LocationGraphLink) => link.visual_distance ?? 120);
    }
    graphRef.current.d3ReheatSimulation();
  }, [graph]);

  const selectedNode = useMemo(() => {
    if (!graph || !selectedId) return null;
    return graph.nodes.find((node) => node.id === selectedId) ?? null;
  }, [graph, selectedId]);

  const selectedLinks = useMemo(() => {
    if (!graph || !selectedId) return [];
    return graph.links
      .filter((link) => getNodeId(link.source) === selectedId || getNodeId(link.target) === selectedId)
      .sort((a, b) => b.strength - a.strength);
  }, [graph, selectedId]);

  const selectedNeighborIds = useMemo(() => {
    const ids = new Set<string>();
    for (const link of selectedLinks) {
      ids.add(getNodeId(link.source));
      ids.add(getNodeId(link.target));
    }
    return ids;
  }, [selectedLinks]);

  function runSearch(nextQuery: string) {
    setQuery(nextQuery);
    const normalizedQuery = nextQuery.trim().toLowerCase();
    if (!graph || normalizedQuery.length < 2) {
      setSelectedId(null);
      return;
    }

    const match = graph.nodes.find(
      (node) =>
        node.barcode.toLowerCase().includes(normalizedQuery) ||
        node.name.toLowerCase().includes(normalizedQuery),
    );
    setSelectedId(match?.id ?? null);
  }

  async function handleRebuild() {
    setRebuilding(true);
    setMessageTone("info");
    setMessage("Recriando grafo de localizacao...");
    try {
      const payload = await rebuildLocationGraph({
        start_at: startAt.trim() || null,
        temporal_decay: temporalDecay,
        half_life_days: halfLifeDays,
        decay_min_weight: 0.01,
      });
      setGraph(payload);
      setSelectedId(null);
      setMessageTone("success");
      setMessage("Grafo recriado com sucesso.");
    } catch (error) {
      const detail =
        error instanceof ApiError
          ? error.message
          : "Nao foi possivel recriar o grafo de localizacao.";
      setMessageTone("error");
      setMessage(detail);
    } finally {
      setRebuilding(false);
    }
  }

  return (
    <main className="graph-debug-shell">
      <aside className="graph-debug-panel">
        <div>
          <p className="eyebrow">Debug do algoritmo</p>
          <h1>Grafo de localização</h1>
        </div>

        <label className="graph-field">
          <span>Buscar produto</span>
          <input
            onChange={(event) => runSearch(event.target.value)}
            placeholder="Nome ou barcode"
            type="search"
            value={query}
          />
        </label>

        <div className="graph-rebuild-box">
          <label className="graph-field">
            <span>Treinar a partir de</span>
            <input
              onChange={(event) => setStartAt(event.target.value)}
              placeholder="2026-04-01T00:00:00+00:00"
              type="text"
              value={startAt}
            />
          </label>
          <label className="graph-toggle">
            <input
              checked={temporalDecay}
              onChange={(event) => setTemporalDecay(event.target.checked)}
              type="checkbox"
            />
            <span>Decaimento temporal</span>
          </label>
          <label className="graph-field">
            <span>Meia-vida em dias</span>
            <input
              min={1}
              onChange={(event) => setHalfLifeDays(Number(event.target.value))}
              type="number"
              value={halfLifeDays}
            />
          </label>
          <button
            className="touch-button touch-button--primary"
            disabled={rebuilding}
            onClick={() => void handleRebuild()}
            type="button"
          >
            {rebuilding ? "Recriando..." : "Recriar grafo"}
          </button>
        </div>

        {message ? <div className={`graph-message graph-message--${messageTone}`}>{message}</div> : null}

        <section className="graph-stats">
          <h2>Treino</h2>
          <dl>
            <div>
              <dt>Nós</dt>
              <dd>{graph?.meta.node_count as number | undefined ?? "-"}</dd>
            </div>
            <div>
              <dt>Arestas</dt>
              <dd>{graph?.meta.edge_count as number | undefined ?? "-"}</dd>
            </div>
            <div>
              <dt>Transições válidas</dt>
              <dd>{graph?.meta.valid_transition_count as number | undefined ?? "-"}</dd>
            </div>
            <div>
              <dt>Threshold inferior</dt>
              <dd>{formatSeconds(graph?.meta.lower_threshold_seconds as number | undefined)}</dd>
            </div>
          </dl>
        </section>

        <section className="graph-selection">
          <h2>Produto</h2>
          {selectedNode ? (
            <>
              <strong>{selectedNode.name}</strong>
              <p>
                Barcode {selectedNode.barcode}
                {selectedNode.aisle ? ` • Corredor ${selectedNode.aisle}` : ""}
              </p>
              <div className="graph-neighbors">
                {selectedLinks.slice(0, 8).map((link) => {
                  const neighborId =
                    getNodeId(link.source) === selectedNode.id
                      ? getNodeId(link.target)
                      : getNodeId(link.source);
                  const neighbor = graph?.nodes.find((node) => node.id === neighborId);
                  return (
                    <article key={`${getNodeId(link.source)}-${getNodeId(link.target)}`}>
                      <span>{neighbor?.name ?? neighborId}</span>
                      <small>
                        {formatSeconds(link.avg_elapsed_seconds)} • {link.transition_count} scans
                      </small>
                    </article>
                  );
                })}
              </div>
            </>
          ) : (
            <p>Busque um produto para destacar sua posição e vizinhos.</p>
          )}
        </section>
      </aside>

      <section className="graph-canvas-shell">
        {loading ? (
          <div className="graph-empty-state">Carregando grafo...</div>
        ) : graph ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={graph}
            linkColor={(link) =>
              selectedId &&
              (getNodeId((link as LocationGraphLink).source) === selectedId ||
                getNodeId((link as LocationGraphLink).target) === selectedId)
                ? "#ef7d22"
                : "rgba(95, 112, 131, 0.42)"
            }
            linkLabel={(link) => linkLabel(link as LocationGraphLink)}
            linkWidth={(link) => {
              const typedLink = link as LocationGraphLink;
              const connected =
                selectedId &&
                (getNodeId(typedLink.source) === selectedId || getNodeId(typedLink.target) === selectedId);
              return connected ? 3 : Math.max(1, Math.min(typedLink.transition_count / 8, 4));
            }}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const typedNode = node as LocationGraphNode & { x: number; y: number };
              const selected = typedNode.id === selectedId;
              const connected = selectedNeighborIds.has(typedNode.id);
              const radius = selected ? 9 : connected ? 6 : 4.5;
              ctx.beginPath();
              ctx.arc(typedNode.x, typedNode.y, radius, 0, 2 * Math.PI, false);
              ctx.fillStyle = selected ? "#ef7d22" : connected ? "#1f8a70" : "#2f5d7c";
              ctx.fill();
              ctx.lineWidth = selected ? 3 : 1;
              ctx.strokeStyle = selected ? "#ffffff" : "rgba(255,255,255,0.72)";
              ctx.stroke();

              if (selected || connected || globalScale > 1.1) {
                const label = typedNode.name;
                const fontSize = Math.max(8, 11 / globalScale);
                ctx.font = `${fontSize}px sans-serif`;
                ctx.fillStyle = "#17202a";
                ctx.fillText(label, typedNode.x + radius + 3, typedNode.y + radius + 3);
              }
            }}
            nodeLabel={(node) => nodeLabel(node as LocationGraphNode)}
            onNodeClick={(node) => {
              const typedNode = node as LocationGraphNode;
              setSelectedId(typedNode.id);
              setQuery(typedNode.name);
            }}
          />
        ) : (
          <div className="graph-empty-state">Nenhum grafo treinado ainda.</div>
        )}
      </section>
    </main>
  );
}
