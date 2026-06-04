const express = require('express');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 3000;
const API_BASE = (process.env.API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
const PUBLIC = path.join(__dirname, 'public');

const app = express();

function sendHtml(res, file) {
  let html;
  try {
    html = fs.readFileSync(path.join(PUBLIC, file), 'utf8');
  } catch (e) {
    return res.status(500).type('html').send(`<h1>${file} 을(를) 찾을 수 없습니다.</h1>`);
  }
  const inject = `<script>window.__API_BASE__=${JSON.stringify(API_BASE)};</script>`;
  html = html.includes('</head>') ? html.replace('</head>', `${inject}</head>`) : inject + html;
  res.set('Cache-Control', 'no-store');
  res.type('html').send(html);
}

app.get('/healthz', (_req, res) => res.json({ status: 'ok', api_base: API_BASE }));
app.get('/', (_req, res) => sendHtml(res, 'app.html'));
app.get('/trace', (_req, res) => sendHtml(res, 'trace_hub.html'));
app.get('/:sid/trace', (_req, res) => sendHtml(res, 'trace.html'));

app.listen(PORT, () => console.log(`[web] listening on :${PORT} → API_BASE=${API_BASE}`));
