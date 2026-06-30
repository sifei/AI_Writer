import { spawn } from "node:child_process";
import path from "node:path";
import { NextResponse } from "next/server";
import type { ExtractedUpload } from "@/lib/types";

const MAX_UPLOAD_BASE64_CHARS = 12_000_000;

type ExtractPayload = {
  fileName?: string;
  mimeType?: string;
  fileBase64?: string;
};

function runWorker(input: ExtractPayload): Promise<ExtractedUpload> {
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
        resolve(JSON.parse(stdout) as ExtractedUpload);
      } catch (error) {
        reject(error);
      }
    });

    child.stdin.write(JSON.stringify({ ...input, command: "extract_upload" }));
    child.stdin.end();
  });
}

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as ExtractPayload;

    if (!payload.fileBase64 || payload.fileBase64.length > MAX_UPLOAD_BASE64_CHARS) {
      return NextResponse.json({ error: "Upload a .docx, .txt, or .tex file under the local size limit." }, { status: 400 });
    }

    const result = await runWorker(payload);
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown extraction failure";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
