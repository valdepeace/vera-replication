import type { RawTrace, RunSnapshot } from './types';

export type TreeNodeData = {
	label: string;
	score: number | null;
	evaluated: boolean;
	branch: number;
	attempt: number;
};

export type TreeNode = {
	id: string;
	position: { x: number; y: number };
	data: TreeNodeData;
};

export type TreeEdge = { id: string; source: string; target: string };

const COL_W = 190;
const ROW_H = 90;

/** Un nodo por celda, columnas por rama y filas por intento; aristas padre → hijo. */
export function buildTree(trace: RawTrace): { nodes: TreeNode[]; edges: TreeEdge[] } {
	const ids = new Set(trace.nodes.map((n) => n.id));
	const nodes: TreeNode[] = trace.nodes.map((n) => {
		const score = n.raw.evaluated ? n.raw.combinedScore : null;
		return {
			id: n.id,
			position: { x: n.branch * COL_W, y: n.attempt * ROW_H },
			data: {
				label: `${n.id}\n${n.status === 'pending' && !n.raw.evaluated ? 'pendiente' : score === null ? 'sin dato' : score}`,
				score,
				evaluated: n.raw.evaluated,
				branch: n.branch,
				attempt: n.attempt
			}
		};
	});
	const edges: TreeEdge[] = trace.nodes
		.filter((n) => n.parentId !== null && ids.has(n.parentId))
		.map((n) => ({ id: `${n.parentId}->${n.id}`, source: n.parentId as string, target: n.id }));
	return { nodes, edges };
}

/** Mejor puntuación evaluada de cada ronda; `null` si la ronda no se pudo leer o no tiene ninguna. */
export function bestByRound(run: RunSnapshot): Array<number | null> {
	return run.rounds.map((round) => {
		if (!round.trace) return null;
		let best: number | null = null;
		for (const node of round.trace.nodes) {
			const score = node.raw.evaluated ? node.raw.combinedScore : null;
			if (score !== null && (best === null || score > best)) best = score;
		}
		return best;
	});
}

/** Dos ejecuciones comparten E0 si su primera ronda tiene las mismas celdas con las mismas puntuaciones. */
export function sharesE0(a: RunSnapshot | undefined, b: RunSnapshot | undefined): boolean {
	const ta = a?.rounds[0]?.trace;
	const tb = b?.rounds[0]?.trace;
	if (!ta || !tb || ta.nodes.length !== tb.nodes.length) return false;
	const byId = new Map(tb.nodes.map((n) => [n.id, n]));
	return ta.nodes.every((n) => {
		const other = byId.get(n.id);
		return (
			other !== undefined &&
			other.raw.evaluated === n.raw.evaluated &&
			other.raw.combinedScore === n.raw.combinedScore
		);
	});
}

/** Directorio del intento, relativo a la raíz del workspace (README del repo oficial). */
export function nodeDir(roundName: string, branch: number, attempt: number): string {
	const base = roundName === '_current' ? '' : `history/${roundName}/`;
	return `${base}explore_b${branch}/attempt_${String(attempt).padStart(2, '0')}`;
}
