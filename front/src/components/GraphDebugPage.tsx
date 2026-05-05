import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import { ApiError, fetchLocationGraph, fetchLocationGraphLinkDetails } from "../lib/api";
import type {
  LocationGraphLink,
  LocationGraphLinkDetails,
  LocationGraphNode,
  LocationGraphPayload,
} from "../lib/types";

const AISLE_COLORS = ["#2f5d7c", "#4f86a6", "#1f8a70", "#7b5fb2", "#c16b2f", "#b23a48"];
const CATEGORY_COLORS = ["#24516b", "#3f8c9f", "#5c7cfa", "#c77dff", "#ef7d22", "#2d6a4f"];
const BASE_NODE_COLOR = "#2f5d7c";
const CONNECTED_NODE_COLOR = "#1f8a70";
const SELECTED_NODE_COLOR = "#ef7d22";

function getNodeId(value: string | LocationGraphNode): string {
  return typeof value === "string" ? value : value.id;
}

function normalizeGroupValue(value?: string | null): string | null {
  const normalized = value?.trim().toLowerCase();
  return normalized ? normalized : null;
}

function buildColorMap(
  nodes: LocationGraphNode[],
  getValue: (node: LocationGraphNode) => string | null,
  palette: string[],
): Map<string, string> {
  const values = Array.from(new Set(nodes.map(getValue).filter((value): value is string => Boolean(value))));
  return new Map(values.map((value, index) => [value, palette[index % palette.length]]));
}

function formatSeconds(value: number | null | undefined): string {
  if (value == null) return "-";
  if (value < 60) return `${value.toFixed(1)}s`;
  return `${(value / 60).toFixed(1)}min`;
}

function formatSampleCount(value: number | null | undefined): string {
  if (value == null) return "-";
  return `${value} amostras`;
}

function getLinkSampleCount(link: LocationGraphLink): number | null {
  return link.analysis?.sample_count_initial ?? null;
}

function getLinkFinalSampleCount(link: LocationGraphLink | LocationGraphLinkDetails): number | null {
  if ("transition_count" in link) {
    return link.analysis?.sample_count_final ?? link.transition_count;
  }

  return link.analysis.sample_count_final ?? link.link.transition_count;
}

function nodeLabel(node: LocationGraphNode): string {
  return `${node.name}\nBarcode ${node.barcode}${node.aisle ? `\nCorredor ${node.aisle}` : ""}`;
}

function linkLabel(link: LocationGraphLink): string {
  const analysis = (link as LocationGraphLink & { analysis?: { branch?: string; decision?: string } }).analysis;
  return [
    `${getNodeId(link.source)} -> ${getNodeId(link.target)}`,
    `Tempo medio: ${formatSeconds(link.avg_elapsed_seconds)}`,
    `Amostras: ${formatSampleCount(getLinkFinalSampleCount(link))}`,
    analysis?.branch ? `Branch: ${analysis.branch}` : null,
    analysis?.decision ? `Decisao: ${analysis.decision}` : null,
  ]
    .filter((line): line is string => Boolean(line))
    .join("\n");
}

function getNodeIdFromLink(link: LocationGraphLink): [string, string] {
  return [getNodeId(link.source), getNodeId(link.target)];
}

function canonicalLinkKey(link: LocationGraphLink): string {
  return getNodeIdFromLink(link).sort().join("::");
}

function formatIsoDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR", { hour12: false });
}

export function GraphDebugPage() {
  const graphRef = useRef<any>(null);
  const detailDragOffsetRef = useRef<{ x: number; y: number } | null>(null);
  const [graph, setGraph] = useState<LocationGraphPayload | null>(null);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedLinkKey, setSelectedLinkKey] = useState<string | null>(null);
  const [linkDetails, setLinkDetails] = useState<LocationGraphLinkDetails | null>(null);
  const [linkLoading, setLinkLoading] = useState(false);
  const [binWidthSeconds, setBinWidthSeconds] = useState(0.1);
  const [detailWindow, setDetailWindow] = useState({ x: 48, y: 120, width: 560, height: 640 });
  const [isDraggingDetail, setIsDraggingDetail] = useState(false);
  const [colorByAisle, setColorByAisle] = useState(true);
  const [colorByCategory, setColorByCategory] = useState(false);
  const [loading, setLoading] = useState(true);
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

  const aisleColors = useMemo(() => {
    if (!graph) return new Map<string, string>();
    return buildColorMap(graph.nodes, (node) => normalizeGroupValue(node.aisle), AISLE_COLORS);
  }, [graph]);

  const categoryColors = useMemo(() => {
    if (!graph) return new Map<string, string>();
    return buildColorMap(graph.nodes, (node) => normalizeGroupValue(node.category), CATEGORY_COLORS);
  }, [graph]);

  const selectedNode = useMemo(() => {
    if (!graph || !selectedId) return null;
    return graph.nodes.find((node) => node.id === selectedId) ?? null;
  }, [graph, selectedId]);

  const selectedLinks = useMemo(() => {
    if (!graph || !selectedId) return [];
    const unique = new Map<string, LocationGraphLink>();
    for (const link of graph.links) {
      if (getNodeId(link.source) !== selectedId && getNodeId(link.target) !== selectedId) continue;
      const key = canonicalLinkKey(link);
      if (!unique.has(key)) unique.set(key, link);
    }
    return Array.from(unique.values()).sort((a, b) => {
      const timeDelta = (a.avg_elapsed_seconds ?? Number.POSITIVE_INFINITY) - (b.avg_elapsed_seconds ?? Number.POSITIVE_INFINITY);
      if (timeDelta !== 0) return timeDelta;

      const aNeighborId = getNodeId(a.source) === selectedId ? getNodeId(a.target) : getNodeId(a.source);
      const bNeighborId = getNodeId(b.source) === selectedId ? getNodeId(b.target) : getNodeId(b.source);
      const aNeighborName = graph.nodes.find((node) => node.id === aNeighborId)?.name ?? "";
      const bNeighborName = graph.nodes.find((node) => node.id === bNeighborId)?.name ?? "";
      const nameDelta = aNeighborName.localeCompare(bNeighborName, "pt-BR");
      if (nameDelta !== 0) return nameDelta;

      return canonicalLinkKey(a).localeCompare(canonicalLinkKey(b));
    });
  }, [graph, selectedId]);

  const selectedLink = useMemo(() => {
    if (!selectedLinkKey) return null;
    return selectedLinks.find((link) => canonicalLinkKey(link) === selectedLinkKey) ?? null;
  }, [selectedLinkKey, selectedLinks]);

  const selectedNeighborIds = useMemo(() => {
    const ids = new Set<string>();
    for (const link of selectedLinks) {
      ids.add(getNodeId(link.source));
      ids.add(getNodeId(link.target));
    }
    return ids;
  }, [selectedLinks]);

  const selectedLinkNeighborId = useMemo(() => {
    if (!selectedLink || !selectedNode) return null;
    const sourceId = getNodeId(selectedLink.source);
    const targetId = getNodeId(selectedLink.target);
    if (sourceId === selectedNode.id) return targetId;
    if (targetId === selectedNode.id) return sourceId;
    return null;
  }, [selectedLink, selectedNode]);

  function getNodeColor(node: LocationGraphNode, selected: boolean, connected: boolean): string {
    if (selected) return SELECTED_NODE_COLOR;

    if (colorByAisle) {
      const aisle = normalizeGroupValue(node.aisle);
      if (aisle) return aisleColors.get(aisle) ?? BASE_NODE_COLOR;
    }

    if (colorByCategory) {
      const category = normalizeGroupValue(node.category);
      if (category) return categoryColors.get(category) ?? BASE_NODE_COLOR;
    }

    return connected ? CONNECTED_NODE_COLOR : BASE_NODE_COLOR;
  }

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

  async function loadLinkDetails(link: LocationGraphLink) {
    const [source, target] = getNodeIdFromLink(link);
    const key = canonicalLinkKey(link);
    setSelectedLinkKey(key);
    setLinkLoading(true);
    setMessage(null);
    try {
      const details = await fetchLocationGraphLinkDetails(source, target);
      setLinkDetails(details);
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : "Nao foi possivel carregar o detalhe do link.";
      setMessageTone("error");
      setMessage(detail);
      setLinkDetails(null);
    } finally {
      setLinkLoading(false);
    }
  }

  function isLinkSelected(link: LocationGraphLink): boolean {
    if (!selectedLinkKey) return false;
    return canonicalLinkKey(link) === selectedLinkKey;
  }

  function startDetailDrag(event: React.PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("button, input, label")) return;
    detailDragOffsetRef.current = {
      x: event.clientX - detailWindow.x,
      y: event.clientY - detailWindow.y,
    };
    setIsDraggingDetail(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveDetailWindow(clientX: number, clientY: number) {
    const offset = detailDragOffsetRef.current;
    if (!offset) return;
    const nextX = Math.max(16, clientX - offset.x);
    const nextY = Math.max(16, clientY - offset.y);
    setDetailWindow((current) => ({ ...current, x: nextX, y: nextY }));
  }

  function endDetailDrag() {
    detailDragOffsetRef.current = null;
    setIsDraggingDetail(false);
  }

  useEffect(() => {
    if (!isDraggingDetail) return;

    function handleMove(event: PointerEvent) {
      moveDetailWindow(event.clientX, event.clientY);
    }

    function handleUp() {
      endDetailDrag();
    }

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    window.addEventListener("pointercancel", handleUp);

    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      window.removeEventListener("pointercancel", handleUp);
    };
  }, [isDraggingDetail]);

  const histogramBins = useMemo(() => {
    if (!linkDetails) return [];
    const width = Math.max(binWidthSeconds, 0.01);
    const bins = new Map<number, { time: number; count: number; kept: number; discarded: number }>();

    for (const sample of linkDetails.samples) {
      const time = Math.floor(sample.elapsed_seconds / width) * width;
      const key = Number(time.toFixed(4));
      const current = bins.get(key) ?? { time: key, count: 0, kept: 0, discarded: 0 };
      current.count += 1;
      if (sample.kept_after_lower && sample.kept_after_upper) current.kept += 1;
      else current.discarded += 1;
      bins.set(key, current);
    }

    return Array.from(bins.values()).sort((a, b) => a.time - b.time);
  }, [binWidthSeconds, linkDetails]);

  const histogramMaxCount = useMemo(() => {
    return Math.max(1, ...histogramBins.map((bin) => bin.count));
  }, [histogramBins]);

  const histogramMaxTime = useMemo(() => {
    if (!linkDetails) return 1;
    return Math.max(
      1,
      ...linkDetails.samples.map((sample) => sample.elapsed_seconds),
      linkDetails.analysis.upper_threshold_seconds ?? 0,
      linkDetails.analysis.lower_threshold_seconds ?? 0,
      linkDetails.analysis.weight_seconds ?? 0,
    );
  }, [linkDetails]);

  const analysisTitle = useMemo(() => {
    if (!linkDetails) return "";
    switch (linkDetails.analysis.branch) {
      case "low_volume":
        return "Descartado por volume inicial";
      case "median":
        return "Mediana do link";
      case "fallback_log_iqr":
        return "Fallback log/IQR";
      case "kde_bimodal":
        return "KDE bimodal";
      case "kde_unimodal":
        return "KDE unimodal";
      case "kde_dependency_fallback":
        return "KDE com fallback de dependencias";
      default:
        return linkDetails.analysis.branch;
    }
  }, [linkDetails]);

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

        <section className="graph-filters">
          <h2>Filtros de cor</h2>
          <label className="graph-toggle graph-toggle--card">
            <input
              checked={colorByAisle}
              onChange={(event) => setColorByAisle(event.target.checked)}
              type="checkbox"
            />
            <span>
              <strong>Cor por corredor</strong>
              <small>Produtos no mesmo corredor recebem a mesma cor.</small>
            </span>
          </label>
          <label className="graph-toggle graph-toggle--card">
            <input
              checked={colorByCategory}
              onChange={(event) => setColorByCategory(event.target.checked)}
              type="checkbox"
            />
            <span>
              <strong>Cor por tipo</strong>
              <small>Produtos do mesmo tipo ficam com a mesma cor.</small>
            </span>
          </label>
        </section>

        {message ? <div className={`graph-message graph-message--${messageTone}`}>{message}</div> : null}

        <section className="graph-selection">
          <h2>Produto selecionado</h2>
          {selectedNode ? (
            <>
              <article className="graph-selection-product">
                <p className="graph-selection-kicker">Produto em destaque</p>
                <strong>{selectedNode.name}</strong>
                <p>Barcode {selectedNode.barcode}</p>
                <div className="graph-selection-meta">
                  {selectedNode.aisle ? <span>Corredor {selectedNode.aisle}</span> : null}
                  {selectedNode.category ? <span>Tipo {selectedNode.category}</span> : null}
                </div>
              </article>

              <div className="graph-selection-links">
                <h3>Links do produto</h3>
                <div className="graph-neighbors">
                  {selectedLinks.map((link) => {
                    const sourceId = getNodeId(link.source);
                    const targetId = getNodeId(link.target);
                    const neighborId = sourceId === selectedNode.id ? targetId : sourceId;
                    const neighbor = graph?.nodes.find((node) => node.id === neighborId);
                    const key = [sourceId, targetId].sort().join("::");
                    return (
                      <button
                        className={`graph-link-card ${selectedLinkKey === key ? "graph-link-card--active" : ""}`}
                        key={key}
                        onClick={() => void loadLinkDetails(link)}
                        type="button"
                      >
                        <span>{neighbor?.name ?? neighborId}</span>
                        <small>
                          {sourceId} → {targetId} • {formatSeconds(link.avg_elapsed_seconds)} • {formatSampleCount(getLinkSampleCount(link))}
                        </small>
                      </button>
                    );
                  })}
                </div>
              </div>
            </>
          ) : (
            <p>Busque um produto para destacar sua posição e vizinhos.</p>
          )}
        </section>
      </aside>

      {selectedLink && linkDetails ? (
        <aside
          className={`graph-float-panel graph-float-panel--link-detail ${isDraggingDetail ? "graph-float-panel--dragging" : ""}`}
          style={{ left: detailWindow.x, top: detailWindow.y, width: detailWindow.width, height: detailWindow.height }}
        >
          <div
            className="graph-float-panel__header"
            onPointerDown={startDetailDrag}
          >
            <div>
              <h2>Detalhe do link</h2>
              <p>{getNodeId(selectedLink.source)} → {getNodeId(selectedLink.target)}</p>
            </div>
            <button
              className="touch-button touch-button--ghost"
              onClick={() => {
                setLinkDetails(null);
                setSelectedLinkKey(null);
              }}
              type="button"
            >
              Fechar
            </button>
          </div>

          <div className="graph-float-panel__body">
            <div className="graph-selection-product">
              <p className="graph-selection-kicker">Link selecionado</p>
              <strong>
                {getNodeId(selectedLink.source)} → {getNodeId(selectedLink.target)}
              </strong>
              <p>
                {formatSeconds(selectedLink.avg_elapsed_seconds)} • {formatSampleCount(linkDetails.analysis.sample_count_initial)} observadas • {formatSampleCount(getLinkFinalSampleCount(linkDetails))} no cálculo
              </p>
              <p>Par consolidado: {canonicalLinkKey(selectedLink)}</p>
            </div>

            <div className="graph-scatter-panel">
              <label className="graph-field graph-field--inline">
                <span>Margem de agrupamento</span>
                <input
                  min={0.01}
                  onChange={(event) => setBinWidthSeconds(Math.max(0.01, Number(event.target.value) || 0.1))}
                  step={0.01}
                  type="number"
                  value={binWidthSeconds}
                />
              </label>
              <svg viewBox="0 0 320 180" className="graph-scatter">
                <line x1="32" y1="148" x2="300" y2="148" className="graph-axis" />
                <line x1="32" y1="20" x2="32" y2="148" className="graph-axis" />
                <text x="166" y="172" textAnchor="middle" className="graph-axis-label">Tempo (s)</text>
                <text x="10" y="84" textAnchor="middle" className="graph-axis-label" transform="rotate(-90 10 84)">Quantidade</text>
                {linkDetails.analysis.lower_threshold_seconds != null ? (
                  <>
                    <line
                      x1={32 + (linkDetails.analysis.lower_threshold_seconds / histogramMaxTime) * 268}
                      x2={32 + (linkDetails.analysis.lower_threshold_seconds / histogramMaxTime) * 268}
                      y1="20"
                      y2="148"
                      className="graph-threshold graph-threshold--lower"
                    />
                    <text
                      x={32 + (linkDetails.analysis.lower_threshold_seconds / histogramMaxTime) * 268}
                      y="16"
                      textAnchor="middle"
                      className="graph-threshold-label"
                    >
                      {formatSeconds(linkDetails.analysis.lower_threshold_seconds)}
                    </text>
                  </>
                ) : null}
                {linkDetails.analysis.upper_threshold_seconds != null ? (
                  <>
                    <line
                      x1={32 + (linkDetails.analysis.upper_threshold_seconds / histogramMaxTime) * 268}
                      x2={32 + (linkDetails.analysis.upper_threshold_seconds / histogramMaxTime) * 268}
                      y1="20"
                      y2="148"
                      className="graph-threshold graph-threshold--upper"
                    />
                    <text
                      x={32 + (linkDetails.analysis.upper_threshold_seconds / histogramMaxTime) * 268}
                      y="16"
                      textAnchor="middle"
                      className="graph-threshold-label graph-threshold-label--upper"
                    >
                      {formatSeconds(linkDetails.analysis.upper_threshold_seconds)}
                    </text>
                  </>
                ) : null}
                {histogramBins.map((bin) => {
                  const barWidth = Math.max(7, (binWidthSeconds / histogramMaxTime) * 268);
                  const barHeight = (bin.count / histogramMaxCount) * 108;
                  const x = 32 + (bin.time / histogramMaxTime) * 268;
                  const y = 148 - barHeight;
                  const kept =
                    linkDetails.analysis.lower_threshold_seconds == null
                      ? true
                      : bin.time >= linkDetails.analysis.lower_threshold_seconds;
                  return (
                    <g key={bin.time}>
                      <rect
                        x={x}
                        y={y}
                        width={barWidth}
                        height={barHeight}
                        rx="3"
                        className={kept ? "graph-bar graph-bar--kept" : "graph-bar graph-bar--discarded"}
                      />
                      <text x={x + barWidth / 2} y={y - 4} textAnchor="middle" className="graph-bar-label">
                        {bin.count}
                      </text>
                      <text x={x + barWidth / 2} y={162} textAnchor="middle" className="graph-bin-label">
                        {bin.time.toFixed(binWidthSeconds < 1 ? 1 : 0)}s
                      </text>
                    </g>
                  );
                })}
              </svg>
              <div className="graph-scatter-legend">
                <span><i className="graph-bar" /> Mantido</span>
                <span><i className="graph-bar graph-bar--discarded" /> Descartado</span>
                <span><i className="graph-threshold graph-threshold--lower" /> Threshold</span>
              </div>
            </div>

            {linkLoading ? <p>Carregando detalhe do link...</p> : null}

            <div className="graph-analysis">
              <p>
                Metodo: <strong>{analysisTitle}</strong>
              </p>
              <p>
                Lower threshold: <strong>{formatSeconds(linkDetails.analysis.lower_threshold_seconds)}</strong>
                {linkDetails.analysis.upper_threshold_seconds != null ? (
                  <> • Upper threshold: <strong>{formatSeconds(linkDetails.analysis.upper_threshold_seconds)}</strong></>
                ) : null}
              </p>
              <p>
                Amostras observadas: {linkDetails.analysis.sample_count_initial}.
              </p>
              <p>
                Amostras no cálculo: {linkDetails.analysis.sample_count_final}.
              </p>
              <p>
                Cortes: {linkDetails.analysis.discarded_after_lower_threshold} removidas no lower, {linkDetails.analysis.discarded_after_upper_threshold} no upper.
              </p>
              {linkDetails.analysis.weight_seconds != null ? (
                <p>
                  Peso do link: <strong>{formatSeconds(linkDetails.analysis.weight_seconds)}</strong>
                </p>
              ) : null}
              {linkDetails.analysis.formula_summary ? <p>{linkDetails.analysis.formula_summary}</p> : null}
              {linkDetails.analysis.formula_lower ? <p>Lower: {linkDetails.analysis.formula_lower}</p> : null}
              {linkDetails.analysis.formula_upper ? <p>Upper: {linkDetails.analysis.formula_upper}</p> : null}
              {linkDetails.analysis.formula_weight ? <p>Peso: {linkDetails.analysis.formula_weight}</p> : null}
              {linkDetails.analysis.dip_p_value != null ? <p>Dip test p-value: {linkDetails.analysis.dip_p_value.toFixed(4)}</p> : null}
              {linkDetails.analysis.dependency_warning ? <p>{linkDetails.analysis.dependency_warning}</p> : null}
              {linkDetails.analysis.discard_reason ? <p>Link descartado: {linkDetails.analysis.discard_reason}</p> : null}
            </div>

            <div className="graph-neighbors graph-sample-list">
              {linkDetails.samples.map((sample) => (
                <article key={`${sample.cart_id}-${sample.transition_at}`}>
                  <span>{sample.cart_id}</span>
                  <small>
                    {formatSeconds(sample.elapsed_seconds)} • {formatIsoDate(sample.transition_at)} • {sample.kept_after_lower ? "keep lower" : "drop lower"}
                    {sample.kept_after_lower && !sample.kept_after_upper ? " • drop upper" : ""}
                    {sample.used_for_weight ? " • used for weight" : ""}
                  </small>
                </article>
              ))}
            </div>
          </div>
        </aside>
      ) : null}

      <section className="graph-canvas-shell">
        {loading ? (
          <div className="graph-empty-state">Carregando grafo...</div>
        ) : graph ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={graph}
            linkColor={(link) =>
              isLinkSelected(link as LocationGraphLink)
                ? "#d95f02"
                : selectedId &&
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
              const selectedLinkNeighbor = typedNode.id === selectedLinkNeighborId;
              const connected = selectedNeighborIds.has(typedNode.id);
              const radius = selected ? 9 : selectedLinkNeighbor ? 8 : connected ? 6 : 4.5;
              const fillColor = getNodeColor(typedNode, selected, connected);
              ctx.beginPath();
              ctx.arc(typedNode.x, typedNode.y, radius, 0, 2 * Math.PI, false);
              ctx.fillStyle = fillColor;
              ctx.fill();
              ctx.lineWidth = selected ? 3 : selectedLinkNeighbor ? 2.5 : 1;
              ctx.strokeStyle = selected ? "#ffffff" : selectedLinkNeighbor ? "#d95f02" : "rgba(255,255,255,0.72)";
              ctx.stroke();

              if (selected || selectedLinkNeighbor || connected || globalScale > 1.1) {
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
              setSelectedLinkKey(null);
              setLinkDetails(null);
            }}
            onLinkClick={(link) => {
              void loadLinkDetails(link as LocationGraphLink);
            }}
          />
        ) : (
          <div className="graph-empty-state">Nenhum grafo treinado ainda.</div>
        )}
      </section>
    </main>
  );
}
