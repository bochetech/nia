/**
 * Teams Webhook Stub — simula el endpoint de incoming webhook de Microsoft Teams.
 * Recibe Adaptive Cards enviadas por el Handoff Service y las loguea.
 */
const http = require("http");

const PORT = 3001;
const receivedCards = [];

const server = http.createServer((req, res) => {
  // CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method === "POST" && req.url === "/webhook") {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      try {
        const card = JSON.parse(body);
        const timestamp = new Date().toISOString();
        receivedCards.push({ timestamp, card });

        console.log(`\n[${timestamp}] 📨 Teams card received:`);
        console.log(JSON.stringify(card, null, 2));

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok", message: "Card received by Teams stub" }));
      } catch (err) {
        console.error("Parse error:", err);
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid JSON" }));
      }
    });
    return;
  }

  if (req.method === "GET" && req.url === "/cards") {
    // Ver todas las cards recibidas
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ count: receivedCards.length, cards: receivedCards }));
    return;
  }

  if (req.method === "DELETE" && req.url === "/cards") {
    receivedCards.length = 0;
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ cleared: true }));
    return;
  }

  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "healthy", service: "teams-stub", port: PORT }));
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not found" }));
});

server.listen(PORT, () => {
  console.log(`🟢 Teams Webhook Stub running on http://localhost:${PORT}`);
  console.log(`  POST /webhook  — receive adaptive cards`);
  console.log(`  GET  /cards    — list received cards`);
  console.log(`  GET  /health   — health check`);
});
