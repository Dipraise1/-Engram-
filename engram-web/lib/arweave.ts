/**
 * Arweave upload utility for Engram
 *
 * Env vars:
 *   ARWEAVE_KEY   — JWK wallet JSON (generate with: node -e "require('arweave').init({}).wallets.generate().then(k=>console.log(JSON.stringify(k)))")
 *   ARWEAVE_ENV   — "mainnet" (default) | "devnet"
 *
 * Devnet uses arweave.net with a test JWK — data is temporary, no AR tokens needed.
 * Mainnet requires a funded wallet (~$0.01 per MB at current AR prices).
 */

import Arweave from "arweave";
import type { JWKInterface } from "arweave/node/lib/wallet";
import { createHash } from "crypto";

const IS_DEVNET = process.env.ARWEAVE_ENV === "devnet";

const arweave = Arweave.init(
  IS_DEVNET
    ? { host: "arweave.net", port: 443, protocol: "https" }
    : { host: "arweave.net", port: 443, protocol: "https" }
);

function getKey(): JWKInterface {
  const raw = process.env.ARWEAVE_KEY;
  if (!raw) throw new Error("ARWEAVE_KEY env var not set");
  try {
    return JSON.parse(raw) as JWKInterface;
  } catch {
    throw new Error("ARWEAVE_KEY is not valid JSON");
  }
}

export function contentCid(buffer: Buffer): string {
  return "sha256:" + createHash("sha256").update(buffer).digest("hex");
}

export interface ArweaveUploadResult {
  tx_id: string;
  url: string;
  content_cid: string;
  size: number;
}

export async function uploadToArweave(
  buffer: Buffer,
  contentType: string,
  tags: Record<string, string> = {}
): Promise<ArweaveUploadResult> {
  const key: JWKInterface = getKey();

  const tx = await arweave.createTransaction({ data: buffer }, key);

  // Standard content-type tag so gateways serve it correctly
  tx.addTag("Content-Type", contentType);
  tx.addTag("App-Name", "Engram");
  tx.addTag("App-Version", "1.0");

  // Custom tags — queryable via Arweave GraphQL
  for (const [k, v] of Object.entries(tags)) {
    tx.addTag(k, v.slice(0, 128)); // Arweave tag value limit
  }

  await arweave.transactions.sign(tx, key);

  const res = await arweave.transactions.post(tx);
  if (res.status !== 200 && res.status !== 202) {
    throw new Error(`Arweave upload failed: status ${res.status}`);
  }

  const tx_id = tx.id;
  const url = `https://arweave.net/${tx_id}`;

  return {
    tx_id,
    url,
    content_cid: contentCid(buffer),
    size: buffer.length,
  };
}

/**
 * Generate a fresh Arweave wallet and return the JWK + address.
 * Used once during setup — store the JWK as ARWEAVE_KEY env var.
 */
export async function generateWallet(): Promise<{ key: JWKInterface; address: string }> {
  const key = await arweave.wallets.generate();
  const address = await arweave.wallets.jwkToAddress(key);
  return { key, address };
}

export async function getWalletBalance(): Promise<{ address: string; ar: string }> {
  const key: JWKInterface = getKey();
  const address = await arweave.wallets.jwkToAddress(key);
  const winstons = await arweave.wallets.getBalance(address);
  const ar = arweave.ar.winstonToAr(winstons);
  return { address, ar };
}
