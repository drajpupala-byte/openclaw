import express from "express";
import path from "path";
import Anthropic from "@anthropic-ai/sdk";

const app = express();
const PORT = process.env.PORT || 3000;
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

app.use(express.json());
app.use(express.static(path.join(__dirname, "../public")));

// Generate sample OHLCV data for demonstration
function generateCandlestickData(days = 60) {
  const data = [];
  let time = Math.floor(Date.now() / 1000) - days * 86400;
  let close = 150 + Math.random() * 50;

  for (let i = 0; i < days; i++) {
    const open = close;
    const change = (Math.random() - 0.48) * 5;
    close = Math.max(10, open + change);
    const high = Math.max(open, close) + Math.random() * 3;
    const low = Math.min(open, close) - Math.random() * 3;
    const volume = Math.floor(100000 + Math.random() * 500000);

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

// API: get chart data
app.get("/api/chart-data", (_req, res) => {
  res.json(generateCandlestickData(60));
});

// API: Claude market analysis
app.post("/api/analyze", async (req, res) => {
  const { data, symbol } = req.body as { data: ReturnType<typeof generateCandlestickData>; symbol: string };

  if (!data || !Array.isArray(data)) {
    res.status(400).json({ error: "data array is required" });
    return;
  }

  const recent = data.slice(-10);
  const first = recent[0];
  const last = recent[recent.length - 1];
  const priceChange = ((last.close - first.close) / first.close) * 100;
  const high10 = Math.max(...recent.map((d) => d.high));
  const low10 = Math.min(...recent.map((d) => d.low));
  const avgVol = Math.round(recent.reduce((s, d) => s + d.volume, 0) / recent.length);

  const prompt = `You are a technical analyst. Analyze this 10-day price summary for ${symbol || "the asset"}:

- Opening price (10 days ago): $${first.open}
- Current close: $${last.close}
- 10-day price change: ${priceChange.toFixed(2)}%
- 10-day high: $${high10}
- 10-day low: $${low10}
- Average daily volume: ${avgVol.toLocaleString()}

Provide a concise 3-paragraph technical analysis covering:
1. Price trend and momentum
2. Key support/resistance levels
3. Short-term outlook (2-5 days)

Keep it factual and analytical.`;

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");

  const stream = await client.messages.stream({
    model: "claude-opus-4-6",
    max_tokens: 512,
    messages: [{ role: "user", content: prompt }],
  });

  for await (const event of stream) {
    if (
      event.type === "content_block_delta" &&
      event.delta.type === "text_delta"
    ) {
      res.write(`data: ${JSON.stringify({ text: event.delta.text })}\n\n`);
    }
  }

  res.write("data: [DONE]\n\n");
  res.end();
});

app.listen(PORT, () => {
  console.log(`OpenClaw server running at http://localhost:${PORT}`);
  console.log(
    `ANTHROPIC_API_KEY: ${process.env.ANTHROPIC_API_KEY ? "set" : "NOT SET — set it to enable Claude analysis"}`
  );
});
