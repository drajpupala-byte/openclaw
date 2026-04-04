#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// ── Shared chart data logic ─────────────────────────────────────────────────

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

function generateCandlestickData(days = 60, seed = 42): Candle[] {
  // Simple seeded PRNG so the same symbol always returns stable data
  let s = seed;
  const rand = () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };

  const data: Candle[] = [];
  let time = Math.floor(Date.now() / 1000) - days * 86400;
  let close = 100 + rand() * 100;

  for (let i = 0; i < days; i++) {
    const open = close;
    const change = (rand() - 0.48) * 6;
    close = Math.max(5, open + change);
    const high = Math.max(open, close) + rand() * 4;
    const low = Math.min(open, close) - rand() * 4;
    const volume = Math.floor(80000 + rand() * 600000);

    data.push({
      time,
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume,
    });
    time += 86400;
  }
  return data;
}

function symbolSeed(symbol: string): number {
  let h = 5381;
  for (const c of symbol.toUpperCase()) h = ((h << 5) + h) ^ c.charCodeAt(0);
  return Math.abs(h) % 100000;
}

// ── MCP Server ─────────────────────────────────────────────────────────────

const server = new McpServer({
  name: "openclaw",
  version: "1.0.0",
});

// Tool: get raw OHLCV candles
server.tool(
  "get_chart_data",
  "Get OHLCV candlestick data for a symbol. Returns daily candles as JSON.",
  {
    symbol: z.string().default("DEMO").describe("Ticker symbol, e.g. AAPL"),
    days: z.number().int().min(5).max(365).default(60).describe("Number of trading days to return"),
  },
  async ({ symbol, days }) => {
    const data = generateCandlestickData(days, symbolSeed(symbol));
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ symbol: symbol.toUpperCase(), days, candles: data }),
        },
      ],
    };
  }
);

// Tool: get a compact human-readable summary (cheaper on context)
server.tool(
  "get_chart_summary",
  "Get a compact price/volume summary for a symbol — good for quick analysis without loading all candles.",
  {
    symbol: z.string().default("DEMO").describe("Ticker symbol"),
    days: z.number().int().min(5).max(90).default(30).describe("Look-back window in days"),
  },
  async ({ symbol, days }) => {
    const data = generateCandlestickData(days, symbolSeed(symbol));
    const first = data[0];
    const last = data[data.length - 1];
    const priceChange = ((last.close - first.open) / first.open) * 100;
    const high = Math.max(...data.map((d) => d.high));
    const low = Math.min(...data.map((d) => d.low));
    const avgVol = Math.round(data.reduce((s, d) => s + d.volume, 0) / data.length);

    // Simple SMA-20
    const closes = data.map((d) => d.close);
    const sma20 = closes.length >= 20
      ? parseFloat((closes.slice(-20).reduce((a, b) => a + b, 0) / 20).toFixed(2))
      : null;

    // Detect trend (linear regression slope sign)
    const n = closes.length;
    const xMean = (n - 1) / 2;
    const yMean = closes.reduce((a, b) => a + b, 0) / n;
    let num = 0, den = 0;
    for (let i = 0; i < n; i++) {
      num += (i - xMean) * (closes[i] - yMean);
      den += (i - xMean) ** 2;
    }
    const slope = den ? num / den : 0;
    const trend = slope > 0.05 ? "uptrend" : slope < -0.05 ? "downtrend" : "sideways";

    const summary = {
      symbol: symbol.toUpperCase(),
      period_days: days,
      open: first.open,
      close: last.close,
      high,
      low,
      price_change_pct: parseFloat(priceChange.toFixed(2)),
      avg_daily_volume: avgVol,
      sma_20: sma20,
      trend,
      candles: data.map(({ time, open, high, low, close, volume }) => ({
        date: new Date(time * 1000).toISOString().slice(0, 10),
        open, high, low, close, volume,
      })),
    };

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(summary, null, 2),
        },
      ],
    };
  }
);

// ── Start ───────────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
server.connect(transport).then(() => {
  // stderr so it doesn't corrupt the MCP stdio protocol
  process.stderr.write("OpenClaw MCP server running\n");
});
