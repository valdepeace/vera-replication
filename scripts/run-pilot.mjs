import { appendFileSync, cpSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const options = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  options.set(process.argv[index], process.argv[index + 1]);
}

const model = options.get("--model");
if (!model) throw new Error("Uso: node scripts/run-pilot.mjs --model <ollama-model>");

const repetitions = Number(options.get("--repetitions") ?? 3);
const maxRepairs = Number(options.get("--max-repairs") ?? 3);
if (!Number.isSafeInteger(repetitions) || repetitions < 1) throw new Error("--repetitions debe ser >= 1");
if (!Number.isSafeInteger(maxRepairs) || maxRepairs < 0 || maxRepairs > 3) throw new Error("--max-repairs debe estar entre 0 y 3");

const suite = options.get("--suite") ?? "synthetic";
if (!["synthetic", "real"].includes(suite)) throw new Error("--suite debe ser synthetic o real");
const baseUrl = (options.get("--base-url") ?? "http://127.0.0.1:11434").replace(/\/$/, "");
const temperature = 0.7;
const numCtx = 4096;
const numPredict = 2048;
const modelInfo = await findInstalledModel();
if (!modelInfo) throw new Error(`El modelo ${model} no está instalado en Ollama; no se descargó nada.`);
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outputRoot = join(root, "results");
mkdirSync(outputRoot, { recursive: true });
const outputDir = createRunDirectory(outputRoot, suite);
const recordsFile = join(outputDir, "records.jsonl");

const syntheticTargets = [
  {
    language: "python",
    name: "normalize_whitespace",
    fixture: join(root, "benchmarks", "vera01", "python"),
    implementation: "targets.py",
    testFile: "test_generated.py",
    importLine: "from targets import normalize_whitespace",
    testCommand: (file) => ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", file],
    suiteCommand: () => ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
  },
  {
    language: "python",
    name: "chunk_text",
    fixture: join(root, "benchmarks", "vera01", "python"),
    implementation: "targets.py",
    testFile: "test_generated.py",
    importLine: "from targets import chunk_text",
    testCommand: (file) => ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", file],
    suiteCommand: () => ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
  },
  {
    language: "node",
    name: "normalizeWhitespace",
    fixture: join(root, "benchmarks", "vera01", "node"),
    implementation: "targets.mjs",
    testFile: "generated.test.mjs",
    importLine: `import { normalizeWhitespace } from "./targets.mjs";`,
    testCommand: (file) => [process.execPath, "--test", file],
    suiteCommand: () => [process.execPath, "--test"],
  },
  {
    language: "node",
    name: "chunkText",
    fixture: join(root, "benchmarks", "vera01", "node"),
    implementation: "targets.mjs",
    testFile: "generated.test.mjs",
    importLine: `import { chunkText } from "./targets.mjs";`,
    testCommand: (file) => [process.execPath, "--test", file],
    suiteCommand: () => [process.execPath, "--test"],
  },
];

const realTargets = [
  {
    language: "python",
    name: "truncate",
    fixture: join(root, "benchmarks", "vera01", "real", "python"),
    implementation: "wsl_sandbox.py",
    testFile: "test_generated.py",
    importLine: "from wsl_sandbox import truncate",
    testCommand: (file) => ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", file],
    suiteCommand: () => ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
  },
  {
    language: "python",
    name: "to_wsl_path",
    fixture: join(root, "benchmarks", "vera01", "real", "python"),
    implementation: "wsl_evaluator.py",
    testFile: "test_generated.py",
    importLine: "from wsl_evaluator import to_wsl_path",
    testCommand: (file) => ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", file],
    suiteCommand: () => ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
  },
  {
    language: "typescript-node",
    name: "nodeDir",
    fixture: join(root, "benchmarks", "vera01", "real", "node"),
    implementation: "treeModel.ts",
    testFile: "generated.test.ts",
    importLine: `import { nodeDir } from "./treeModel.ts";`,
    testCommand: (file) => [process.execPath, "--experimental-strip-types", "--test", file],
    suiteCommand: () => [process.execPath, "--experimental-strip-types", "--test", "baseline.test.ts", "generated.test.ts"],
  },
  {
    language: "typescript-node",
    name: "bestByRound",
    fixture: join(root, "benchmarks", "vera01", "real", "node"),
    implementation: "treeModel.ts",
    testFile: "generated.test.ts",
    importLine: `import { bestByRound } from "./treeModel.ts";`,
    testCommand: (file) => [process.execPath, "--experimental-strip-types", "--test", file],
    suiteCommand: () => [process.execPath, "--experimental-strip-types", "--test", "baseline.test.ts", "generated.test.ts"],
  },
];

const targets = suite === "real" ? realTargets : syntheticTargets;

const totals = { candidates: 0, directPass: 0, repairPass: 0, repairRounds: 0 };
for (let targetIndex = 0; targetIndex < targets.length; targetIndex += 1) {
  const target = targets[targetIndex];
  const source = readFileSync(join(target.fixture, target.implementation), "utf8");
  const sourceSha256 = createHash("sha256").update(source).digest("hex");
  for (let repetition = 1; repetition <= repetitions; repetition += 1) {
    const seed = 21000 + targetIndex * repetitions + repetition;
    const caseId = `${target.language}-${target.name}-r${repetition}`;
    const caseDir = join(outputDir, caseId);
    mkdirSync(caseDir, { recursive: true });

    const initialPrompt = makeInitialPrompt(target, source);
    writeFileSync(join(caseDir, "initial-prompt.txt"), initialPrompt);
    const initial = await generate(initialPrompt, seed);
    const initialCode = cleanCode(initial.response);
    writeFileSync(join(caseDir, "initial-test.txt"), initialCode);

    const direct = await runBranch(target, caseDir, "direct", initialCode, 0, seed);
    const repair = await runBranch(target, caseDir, "repair", initialCode, maxRepairs, seed);
    const record = {
      caseId,
      suite,
      language: target.language,
      focalMethod: target.name,
      repetition,
      model,
      modelDigest: modelInfo.digest,
      implementationSha256: sourceSha256,
      settings: { endpoint: "/api/chat", think: false, temperature, numCtx, numPredict, seed, maxRepairs, baseUrl },
      initialGeneration: generationSummary(initial),
      direct,
      repair,
      manualAudit: "pending",
    };
    appendFileSync(recordsFile, `${JSON.stringify(record)}\n`);
    totals.candidates += 1;
    if (direct.runnerPass) totals.directPass += 1;
    if (repair.runnerPass) totals.repairPass += 1;
    totals.repairRounds += repair.repairs;
    console.log(`${caseId}: direct=${direct.runnerPass} repair=${repair.runnerPass} rounds=${repair.repairs}`);
  }
}

writeFileSync(join(outputDir, "summary.json"), `${JSON.stringify({ suite, model, repetitions, maxRepairs, totals }, null, 2)}\n`);
console.log(`Resultados: ${relative(root, outputDir)}`);
console.log(JSON.stringify(totals));

async function runBranch(target, caseDir, branchName, initialCode, repairLimit, seed) {
  const workDir = join(caseDir, branchName);
  mkdirSync(workDir, { recursive: true });
  cpSync(target.fixture, workDir, { recursive: true });

  let currentCode = initialCode;
  const attempts = [];
  let repairs = 0;
  for (let attempt = 0; attempt <= repairLimit; attempt += 1) {
    writeFileSync(join(workDir, target.testFile), currentCode);
    const checks = runChecks(target, workDir, caseDir, branchName, attempt);
    const runnerPass = checks.every((check) => check.pass);
    attempts.push({ attempt, runnerPass, checks });
    if (runnerPass || attempt === repairLimit) break;

    const diagnostic = checks.map((check) => `${check.name}\n${check.stdout}\n${check.stderr}`).join("\n").slice(-12000);
    const repairPrompt = makeRepairPrompt(target, currentCode, diagnostic);
    writeFileSync(join(caseDir, branchName, `repair-${attempt + 1}-prompt.txt`), repairPrompt);
    const repairResponse = await generate(repairPrompt, seed + attempt + 1);
    currentCode = cleanCode(repairResponse.response);
    writeFileSync(join(caseDir, branchName, `repair-${attempt + 1}.txt`), currentCode);
    attempts[attempts.length - 1].repairGeneration = generationSummary(repairResponse);
    repairs += 1;
  }

  return {
    runnerPass: attempts.at(-1).runnerPass,
    repairs,
    testFile: relative(root, join(workDir, target.testFile)),
    attempts,
  };
}

function runChecks(target, workDir, caseDir, branchName, attempt) {
  const commands = [
    ["generated-test", target.testCommand(target.testFile)],
    ["full-suite", target.suiteCommand()],
  ];
  return commands.map(([name, [executable, ...args]]) => {
    const result = spawnSync(executable, args, {
      cwd: workDir,
      encoding: "utf8",
      timeout: 300000,
      maxBuffer: 2 * 1024 * 1024,
      windowsHide: true,
    });
    const stdout = result.stdout ?? "";
    const stderr = result.stderr ?? result.error?.message ?? "";
    writeFileSync(join(caseDir, branchName, `attempt-${attempt}-${name}.stdout.txt`), stdout);
    writeFileSync(join(caseDir, branchName, `attempt-${attempt}-${name}.stderr.txt`), stderr);
    const testCount = countTests(target.language, stdout + stderr);
    return {
      name,
      command: [executable, ...args],
      exitCode: result.status,
      testCount,
      pass: result.status === 0 && testCount > 0,
      stdout,
      stderr,
    };
  });
}

async function generate(prompt, seed) {
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      messages: [{ role: "user", content: prompt }],
      think: false,
      stream: false,
      keep_alive: "5m",
      options: { temperature, seed, num_ctx: numCtx, num_predict: numPredict },
    }),
    signal: AbortSignal.timeout(300000),
  });
  if (!response.ok) throw new Error(`Ollama devolvió HTTP ${response.status}: ${await response.text()}`);
  const result = await response.json();
  return { ...result, response: result.message?.content ?? "" };
}

function makeInitialPrompt(target, source) {
  const framework = target.language === "python" ? "pytest" : "node:test y node:assert/strict";
  return `Genera un archivo de tests unitarios para la función ${target.name}.\n` +
    `Usa ${framework}. Importa el método con: ${target.importLine}\n` +
    "Prueba comportamiento normal y casos límite descritos por el código. " +
    "Los tests deben llamar directamente a la función focal y contener aserciones. " +
    "No cambies el código de producción ni uses dependencias externas. " +
    "Devuelve únicamente el contenido completo del archivo de tests, sin Markdown.\n\n" +
    `Código disponible:\n${source}`;
}

function makeRepairPrompt(target, currentCode, diagnostic) {
  return `Repara únicamente el archivo de tests para ${target.name}.\n` +
    `Importación requerida: ${target.importLine}\n` +
    "Devuelve el archivo completo, conserva tests útiles, añade aserciones que llamen a la función focal " +
    "y no cambies el código de producción. Devuelve solo código, sin Markdown.\n\n" +
    `Tests actuales:\n${currentCode}\n\nDiagnóstico del runner:\n${diagnostic}`;
}

function cleanCode(value = "") {
  return value.trim()
    .replace(/^```(?:python|javascript|typescript|js|ts)?\s*/i, "")
    .replace(/\s*```$/, "")
    .trim();
}

function countTests(language, output) {
  const pattern = language === "python"
    ? /(?:^|\s)(\d+)\s+(?:passed|failed|error|errors|skipped|xfailed|xpassed)\b/im
    : /(?:#|ℹ)\s*tests?\s+(\d+)/i;
  return Number(pattern.exec(output)?.[1] ?? 0);
}

function generationSummary(result) {
  return {
    promptTokens: result.prompt_eval_count ?? null,
    outputTokens: result.eval_count ?? null,
    durationNs: result.total_duration ?? null,
    response: result.response ?? "",
  };
}

async function findInstalledModel() {
  const response = await fetch(`${baseUrl}/api/tags`, { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`Ollama no responde en ${baseUrl}: HTTP ${response.status}`);
  const body = await response.json();
  return body.models?.find((entry) => entry.name === model) ?? null;
}

function createRunDirectory(parent, suite) {
  return mkdtempSync(join(parent, `vera01-${suite}-${new Date().toISOString().replaceAll(":", "-")}-`));
}
