import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import { ApiError } from "../lib/api";

// ─── Types ──────────────────────────────────────────────────────────

interface RecommendationGraphNode {
  id: string;
  barcode: string;
  name: string;
  category?: string | null;
  aisle?: string | null;
  purchase_count: number;
  x?: number;
  y?: number;
}

interface RecommendationGraphLink {
  source: string | RecommendationGraphNode;
  target: string | RecommendationGraphNode;
  co_occurrence_count: number;
  support: number;
  confidence_ab: number;
  confidence_ba: number;
  lift: number;
  strength: number;
  visual_distance?: number;
}

interface RecommendationGraphPayload {
  nodes: RecommendationGraphNode[];
  links: RecommendationGraphLink[];
  meta: {
    total_transactions: number;
    total_products: number;
    node_count: number;
    edge_count: number;
    min_cooccurrence: number;
    graph_type: string;
    description: string;
  };
}

// ─── Constants ──────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  mercearia: "#2f5d7c",
  laticinios: "#4f86a6",
  bebidas: "#c16b2f",
  higiene: "#7b5fb2",
  limpeza: "#1f8a70",
  padaria: "#b23a48",
  carnes: "#d4534a",
  hortifruti: "#2d6a4f",
};

const DEFAULT_NODE_COLOR = "#5f7083";
const CONNECTED_NODE_COLOR = "#1f8a70";
const SELECTED_NODE_COLOR = "#ef7d22";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

// ─── Helpers ────────────────────────────────────────────────────────

function getNodeId(value: string | RecommendationGraphNode): string {
  return typeof value === "string" ? value : value.id;
}

function getCategoryColor(category?: string | null): string {
  if (!category) return DEFAULT_NODE_COLOR;
  const key = category.toLowerCase().trim();
  return CATEGORY_COLORS[key] ?? DEFAULT_NODE_COLOR;
}

// ─── Component ──────────────────────────────────────────────────────

export function RecommendationGraphPage() {
  const graphRef = useRef<any>(null);
  const [graph, setGraph] = useState<RecommendationGraphPayload | null>(null);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [colorByCategory, setColorByCategory] = useState(true);
  const [colorByAisle, setColorByAisle] = useState(false);
  const [showLabels, setShowLabels] = useState(true);
  const [minCooccurrence, setMinCooccurrence] = useState(3);

  async function loadGraph(minCo?: number) {
    setLoading(true);
    setMessage(null);
    try {
      const mc = minCo ?? minCooccurrence;
      const response = await fetch(
        `${API_BASE_URL}/recommendation-graph?min_cooccurrence=${mc}`
      );
      if (!response.ok) {
        throw new Error("Nao foi possivel carregar o grafo de recomendacao.");
      }
      const payload: RecommendationGraphPayload = await response.json();
      setGraph(payload);
    } catch (error) {
      setGraph(null);
      setMessage(
        error instanceof Error
          ? error.message
          : "Erro ao carregar o grafo."
      );
    } finally {
      setLoading(false);
    }
  }

  async function rebuildGraph() {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/recommendation-graph/rebuild`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ min_cooccurrence: minCooccurrence }),
        }
      );
      if (!response.ok) {
        throw new Error("Nao foi possivel reconstruir o grafo.");
      }
      const payload: RecommendationGraphPayload = await response.json();
      setGraph(payload);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Erro ao reconstruir."
      );
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
      linkForce.distance(
        (link: RecommendationGraphLink) => link.visual_distance ?? 120
      );
    }
    graphRef.current.d3ReheatSimulation();
  }, [graph]);

  const selectedNode = useMemo(() => {
    if (!graph || !selectedId) return null;
    return graph.nodes.find((n) => n.id === selectedId) ?? null;
  }, [graph, selectedId]);

  const selectedLinks = useMemo(() => {
    if (!graph || !selectedId) return [];
    return graph.links
      .filter(
        (link) =>
          getNodeId(link.source) === selectedId ||
          getNodeId(link.target) === selectedId
      )
      .sort((a, b) => b.co_occurrence_count - a.co_occurrence_count);
  }, [graph, selectedId]);

  const selectedNeighborIds = useMemo(() => {
    const ids = new Set<string>();
    for (const link of selectedLinks) {
      ids.add(getNodeId(link.source));
      ids.add(getNodeId(link.target));
    }
    return ids;
  }, [selectedLinks]);

  const filteredNodes = useMemo(() => {
    if (!graph || !query.trim()) return null;
    const q = query.toLowerCase();
    return graph.nodes.filter(
      (n) =>
        n.name.toLowerCase().includes(q) ||
        n.barcode.includes(q)
    );
  }, [graph, query]);

  function getNodeColor(
    node: RecommendationGraphNode,
    selected: boolean,
    connected: boolean
  ): string {
    if (selected) return SELECTED_NODE_COLOR;
    if (connected) return CONNECTED_NODE_COLOR;
    if (colorByCategory) return getCategoryColor(node.category);
    return DEFAULT_NODE_COLOR;
  }

  return (
    <main
      style={{
        display: "flex",
        height: "100vh",
        fontFamily: "system-ui, -apple-system, sans-serif",
        color: "#17202a",
        background: "#f4f6f8",
      }}
    >
      {/* ─── Sidebar ──────────────────────────────────── */}
      <aside
        style={{
          width: 320,
          minWidth: 320,
          padding: 16,
          borderRight: "1px solid #dfe3e8",
          overflowY: "auto",
          background: "#ffffff",
          fontSize: 13,
        }}
      >
        <h2
          style={{
            fontSize: 12,
            textTransform: "uppercase",
            letterSpacing: 1,
            color: "#5f7083",
            marginBottom: 4,
          }}
        >
          Debug do Algoritmo
        </h2>
        <h1 style={{ fontSize: 18, margin: "0 0 16px" }}>
          Grafo de Recomendacao
        </h1>

        {/* Search */}
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 12, color: "#5f7083" }}>
            Buscar produto
          </label>
          <input
            type="text"
            placeholder="Nome ou barcode"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              const q = e.target.value.toLowerCase();
              if (graph && q.length >= 2) {
                const match = graph.nodes.find(
                  (n) =>
                    n.name.toLowerCase().includes(q) ||
                    n.barcode.includes(q)
                );
                if (match) setSelectedId(match.id);
              }
            }}
            style={{
              width: "100%",
              padding: "8px 10px",
              border: "1px solid #dfe3e8",
              borderRadius: 6,
              fontSize: 13,
              marginTop: 4,
              boxSizing: "border-box",
            }}
          />
        </div>

        {/* Filters */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, color: "#5f7083", display: "block" }}>
            Filtros de cor
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={colorByCategory}
              onChange={() => setColorByCategory(!colorByCategory)}
            />
            Cor por categoria
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showLabels}
              onChange={() => setShowLabels(!showLabels)}
            />
            Mostrar nomes
          </label>
        </div>

        {/* Min co-occurrence */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, color: "#5f7083" }}>
            Co-ocorrencia minima: {minCooccurrence}
          </label>
          <input
            type="range"
            min={1}
            max={20}
            value={minCooccurrence}
            onChange={(e) => setMinCooccurrence(Number(e.target.value))}
            style={{ width: "100%", marginTop: 4 }}
          />
          <button
            onClick={() => void loadGraph(minCooccurrence)}
            style={{
              marginTop: 6,
              padding: "6px 12px",
              fontSize: 12,
              border: "1px solid #dfe3e8",
              borderRadius: 6,
              cursor: "pointer",
              background: "#f4f6f8",
            }}
          >
            Atualizar filtro
          </button>
        </div>

        {/* Rebuild */}
        <button
          onClick={() => void rebuildGraph()}
          disabled={loading}
          style={{
            width: "100%",
            padding: "8px 12px",
            fontSize: 13,
            fontWeight: 500,
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            background: "#2f5d7c",
            color: "#fff",
            marginBottom: 16,
          }}
        >
          {loading ? "Reconstruindo..." : "Reconstruir grafo"}
        </button>

        {/* Selected product */}
        {selectedNode ? (
          <div
            style={{
              background: "#fff8f0",
              border: "1px solid #f0d9b5",
              borderRadius: 8,
              padding: 12,
              marginBottom: 12,
            }}
          >
            <div
              style={{ fontSize: 11, textTransform: "uppercase", color: "#5f7083" }}
            >
              Produto em destaque
            </div>
            <h3 style={{ margin: "4px 0", fontSize: 15 }}>{selectedNode.name}</h3>
            <div style={{ fontSize: 12, color: "#5f7083" }}>
              Barcode {selectedNode.barcode}
              {selectedNode.category && (
                <span
                  style={{
                    display: "inline-block",
                    background: getCategoryColor(selectedNode.category),
                    color: "#fff",
                    padding: "1px 8px",
                    borderRadius: 10,
                    fontSize: 11,
                    marginLeft: 6,
                  }}
                >
                  {selectedNode.category}
                </span>
              )}
              {selectedNode.aisle && (
                <span
                  style={{
                    display: "inline-block",
                    background: "#dfe3e8",
                    padding: "1px 8px",
                    borderRadius: 10,
                    fontSize: 11,
                    marginLeft: 4,
                  }}
                >
                  Corredor {selectedNode.aisle}
                </span>
              )}
            </div>
            <div style={{ fontSize: 12, marginTop: 4, color: "#5f7083" }}>
              Apareceu em {selectedNode.purchase_count} compras
            </div>

            {/* Connected links */}
            <div style={{ marginTop: 12, fontSize: 12 }}>
              <strong>Links do produto</strong>
              {selectedLinks.length === 0 ? (
                <div style={{ color: "#5f7083", marginTop: 4 }}>
                  Nenhuma conexao encontrada.
                </div>
              ) : (
                selectedLinks.map((link, i) => {
                  const neighborId =
                    getNodeId(link.source) === selectedId
                      ? getNodeId(link.target)
                      : getNodeId(link.source);
                  const neighbor = graph?.nodes.find(
                    (n) => n.id === neighborId
                  );
                  return (
                    <article
                      key={i}
                      style={{
                        padding: "6px 0",
                        borderBottom: "1px solid #f0f0f0",
                        cursor: "pointer",
                      }}
                      onClick={() => {
                        setSelectedId(neighborId);
                        if (neighbor) setQuery(neighbor.name);
                      }}
                    >
                      <div style={{ fontWeight: 500 }}>
                        {neighbor?.name ?? neighborId}
                      </div>
                      <small style={{ color: "#5f7083" }}>
                        {neighbor?.aisle && `Corredor ${neighbor.aisle}`}
                        {" - "}Co-ocorrencia: {link.co_occurrence_count}x
                        {" - "}Support: {(link.support * 100).toFixed(1)}%
                        {" - "}Lift: {link.lift.toFixed(2)}
                      </small>
                    </article>
                  );
                })
              )}
            </div>
          </div>
        ) : null}

        {/* Meta */}
        {graph?.meta ? (
          <div style={{ fontSize: 11, color: "#5f7083", marginTop: 8 }}>
            <div>{graph.meta.node_count} produtos</div>
            <div>{graph.meta.edge_count} conexoes</div>
            <div>{graph.meta.total_transactions} transacoes</div>
          </div>
        ) : null}
      </aside>

      {/* ─── Graph canvas ─────────────────────────────── */}
      <section style={{ flex: 1, position: "relative" }}>
        {loading ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              color: "#5f7083",
            }}
          >
            Carregando grafo de recomendacao...
          </div>
        ) : graph ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={graph}
            linkColor={(link) => {
              const typedLink = link as RecommendationGraphLink;
              if (!selectedId) return "rgba(95, 112, 131, 0.25)";
              const src = getNodeId(typedLink.source);
              const tgt = getNodeId(typedLink.target);
              if (src === selectedId || tgt === selectedId) return "#ef7d22";
              return "rgba(95, 112, 131, 0.12)";
            }}
            linkWidth={(link) => {
              const typedLink = link as RecommendationGraphLink;
              const connected =
                selectedId &&
                (getNodeId(typedLink.source) === selectedId ||
                  getNodeId(typedLink.target) === selectedId);
              if (connected) return 3;
              return Math.max(0.5, Math.min(typedLink.co_occurrence_count / 10, 4));
            }}
            linkLabel={(link) => {
              const l = link as RecommendationGraphLink;
              return `Co-ocorrencia: ${l.co_occurrence_count}x | Support: ${(l.support * 100).toFixed(1)}% | Lift: ${l.lift.toFixed(2)}`;
            }}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const typedNode = node as RecommendationGraphNode & {
                x: number;
                y: number;
              };
              const selected = typedNode.id === selectedId;
              const connected = selectedNeighborIds.has(typedNode.id);
              const dimmed =
                selectedId !== null && !selected && !connected;

              // Radius based on purchase count
              const baseRadius = Math.max(
                3,
                Math.min(typedNode.purchase_count / 8, 12)
              );
              const radius = selected ? baseRadius + 4 : connected ? baseRadius + 1 : baseRadius;

              const fillColor = dimmed
                ? "rgba(95, 112, 131, 0.2)"
                : getNodeColor(typedNode, selected, connected);

              ctx.beginPath();
              ctx.arc(typedNode.x, typedNode.y, radius, 0, 2 * Math.PI, false);
              ctx.fillStyle = fillColor;
              ctx.fill();
              ctx.lineWidth = selected ? 3 : 1;
              ctx.strokeStyle = selected
                ? "#ffffff"
                : "rgba(255,255,255,0.72)";
              ctx.stroke();

              // Labels
              if (
                showLabels &&
                (selected || connected || globalScale > 1.1)
              ) {
                const label = typedNode.name;
                const fontSize = Math.max(8, 11 / globalScale);
                ctx.font = `${fontSize}px sans-serif`;
                ctx.fillStyle = dimmed ? "rgba(23,32,42,0.3)" : "#17202a";
                ctx.fillText(
                  label,
                  typedNode.x + radius + 3,
                  typedNode.y + radius + 3
                );
              }
            }}
            nodeLabel={(node) => {
              const n = node as RecommendationGraphNode;
              return `${n.name}\n${n.category ?? ""} | Corredor ${n.aisle ?? "?"}\n${n.purchase_count} compras`;
            }}
            onNodeClick={(node) => {
              const typedNode = node as RecommendationGraphNode;
              setSelectedId(typedNode.id);
              setQuery(typedNode.name);
            }}
            onBackgroundClick={() => {
              setSelectedId(null);
            }}
          />
        ) : (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              color: "#5f7083",
            }}
          >
            {message ?? "Nenhum grafo disponivel. Clique em 'Reconstruir grafo'."}
          </div>
        )}
      </section>
    </main>
  );
}
