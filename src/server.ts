import express from "express";
import path from "path";

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, "../public")));

// Generate OHLCV data (same logic as mcp-server.ts)
function symbolSeed(symbol: string): number {
  let h = 5381;
  for (const c of symbol.toUpperCase()) h = ((h << 5) + h) ^ c.charCodeAt(0);
  return Math.abs(h) % 100000;
}

function generateCandlestickData(days = 60, seed = 42) {
  let s = seed;
  const rand = () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };

  const data = [];
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

// API: chart data (used by the frontend)
app.get("/api/chart-data", (req, res) => {
  const symbol = (req.query.symbol as string) || "DEMO";
  const days = parseInt((req.query.days as string) || "60", 10);
  res.json(generateCandlestickData(Math.min(days, 365), symbolSeed(symbol)));
});

app.listen(PORT, () => {
  console.log(`OpenClaw UI  →  http://localhost:${PORT}`);
  console.log(`MCP server   →  npm run mcp   (then connect via Claude Code settings)`);
});
