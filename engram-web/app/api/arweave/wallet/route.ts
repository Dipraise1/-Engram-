/**
 * GET /api/arweave/wallet
 *
 * Returns the current Arweave wallet address and AR balance.
 * If ARWEAVE_KEY is not set, generates a fresh wallet and returns
 * the JWK so the operator can fund it and set the env var.
 *
 * Only callable server-side / by admins — do not expose publicly.
 */
import { NextResponse } from "next/server";
import { generateWallet, getWalletBalance } from "@/lib/arweave";

export const runtime = "nodejs";

export async function GET() {
  if (!process.env.ARWEAVE_KEY) {
    // No wallet configured — generate one
    const { key, address } = await generateWallet();
    return NextResponse.json({
      status: "no_wallet",
      message: "No ARWEAVE_KEY set. Save the key below as your ARWEAVE_KEY env var, then fund the address with AR.",
      address,
      key, // JWK — treat as a private key, store securely
    });
  }

  try {
    const { address, ar } = await getWalletBalance();
    return NextResponse.json({
      status: "ok",
      address,
      balance_ar: ar,
      env: process.env.ARWEAVE_ENV ?? "mainnet",
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ status: "error", error: msg }, { status: 500 });
  }
}
