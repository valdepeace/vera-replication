export type ParseResult<T> = { ok: true; value: T } | { ok: false; error: string };

/** Resultado crudo de una celda (un intento o el baseline). `null` = sin dato. */
export interface Cell {
	evaluated: boolean;
	combinedScore: number | null;
	nValid: number | null;
	nTotal: number | null;
	error: string | null;
}

export interface RawNode {
	id: string;
	branch: number;
	attempt: number;
	parentId: string | null;
	intent: string;
	tags: string[];
	path: string;
	createdAt: string | null;
	status: string | null;
	raw: Cell;
}

export interface ManifestPolicy {
	name: string | null;
	source: string | null;
	sha256: string | null;
	betaDefault: number | null;
	config: Record<string, unknown>;
}

export interface ManifestExplore {
	maxWorkers: number | null;
	maxWidth: number | null;
	maxRefine: number | null;
	maxSteps: number | null;
	bestScore: number | null;
	probeBudget: number | null;
	decisionRounds: number | null;
	effectiveSequentialRounds: number | null;
	batchSizes: number[];
}

/** `live_cycle_manifest.json` (schema 2 conocido; otros se aceptan y se reportan). */
export interface LiveCycleManifest {
	schemaVersion: number | null;
	cycle: number;
	recordedAt: string | null;
	workspace: string | null;
	policy?: ManifestPolicy;
	explore?: ManifestExplore;
}

export type StrataResult<T> = { ok: true; value: T } | { ok: false; error: string };

export interface StrataHealth {
	status: string;
	loaded: boolean;
	model: string;
	max_context: number;
	api_monitor: boolean;
}

/** Elemento de `GET /api/requests` (sin input/output/reasoning). */
export interface StrataRequestSummary {
	id: string;
	path: string;
	model: string;
	/** epoch en segundos */
	started_at: number;
	state: string;
	stream: boolean;
	wallclock_s?: number;
	[key: string]: unknown;
}

/** Registro completo de `GET /api/requests?id=<id>`. */
export interface StrataRequestRecord extends StrataRequestSummary {
	input: string;
	input_truncated?: boolean;
	output: string;
	reasoning?: string;
	error?: string;
}

/** Estado agregado de Strata para la UI (decidido en el pre-flight del ledger). */
export interface StrataStatus {
	/** URL base de Strata, para enlazar a su monitor. */
	url: string;
	connected: boolean;
	monitorOn: boolean;
	gap: boolean;
	model: string | null;
	queue: number | null;
	tokS: number | null;
	ctxUsed: number | null;
	ctxMax: number | null;
	/** bytes de VRAM (de `hardware.gpu_mem_used/total` en `/metrics`) */
	gpuMemUsed: number | null;
	gpuMemTotal: number | null;
	captured: number;
	lastError: string | null;
}

export interface LearningStep {
	/** Carpeta relativa al workspace, p. ej. `learning/iter000`. */
	dir?: string;
	discoverSummary: Record<string, unknown> | null;
	policyVersions: string[];
}

export interface RoundSnapshot {
	index: number;
	/** `iterNNN` o `_current` (ronda en curso, aún sin archivar). */
	name: string;
	trace: RawTrace | null;
	manifest: LiveCycleManifest | null;
	learning: LearningStep | null;
	issues: string[];
}

export interface RunSnapshot {
	id: string;
	label: string;
	role: 'dream-rsi' | 'baseline' | 'e0';
	root: string;
	state: 'absent' | 'empty' | 'present';
	rounds: RoundSnapshot[];
	tracePool: string[];
	promotedPolicy: { path: string } | null;
	pipelineSummary: Record<string, unknown> | null;
	issues: string[];
	updatedAt: string;
}

export type HubEvent =
	| { type: 'run'; snapshot: RunSnapshot }
	| { type: 'strata'; status: StrataStatus };

export interface RawTrace {
	version: number;
	workspace: string;
	exportedAt: string;
	nProblems: number;
	baseline: Cell;
	nodes: RawNode[];
}
