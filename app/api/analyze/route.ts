import { spawn } from "node:child_process";
import path from "node:path";
import { NextResponse } from "next/server";
import type { AnalysisResult, ManuscriptInput } from "@/lib/types";

const MAX_MANUSCRIPT_CHARS = 80_000;

function validatePayload(payload: Partial<ManuscriptInput>): string | null {
  if (!payload.narrative || payload.narrative.trim().length < 200) {
    return "Please provide at least 200 characters of manuscript text.";
  }

  if (payload.narrative.length > MAX_MANUSCRIPT_CHARS) {
    return "Manuscript text is too long for this local analysis run.";
  }

  return null;
}

function runWorker(input: ManuscriptInput): Promise<AnalysisResult> {
  return new Promise((resolve, reject) => {
    const workerPath = path.join(process.cwd(), "worker", "biomed_assistant", "cli.py");
    const child = spawn("python3", [workerPath], {
      cwd: process.cwd(),
      stdio: ["pipe", "pipe", "pipe"]
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr || `Worker exited with code ${code}`));
        return;
      }

      try {
        resolve(JSON.parse(stdout) as AnalysisResult);
      } catch (error) {
        reject(error);
      }
    });

    child.stdin.write(JSON.stringify(input));
    child.stdin.end();
  });
}

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as Partial<ManuscriptInput>;
    const error = validatePayload(payload);

    if (error) {
      return NextResponse.json({ error }, { status: 400 });
    }

    const input: ManuscriptInput = {
      title: payload.title?.trim(),
      narrative: payload.narrative!.trim(),
      articleType: payload.articleType || "Original Research",
      targetField: payload.targetField || "General biomedicine",
      constraints: payload.constraints || []
    };

    const result = await runWorker(input);
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown analysis failure";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
