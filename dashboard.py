"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MovieBox Pro — by faisaljs</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{--primary:#ff3d71;--secondary:#3366ff;--accent:#00f2ff;--bg:#07080c;--card-bg:rgba(255,255,255,0.03);--glass:rgba(255,255,255,0.06);--text:#fff}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);overflow-x:hidden;min-height:100vh;background-image:radial-gradient(circle at 10% 10%,rgba(255,61,113,0.12) 0%,transparent 40%),radial-gradient(circle at 90% 90%,rgba(51,102,255,0.12) 0%,transparent 40%)}
.container{max-width:1300px;margin:0 auto;padding:60px 24px}
header{text-align:center;margin-bottom:80px;animation:fadeInDown 1s ease-out}
@keyframes fadeInDown{from{opacity:0;transform:translateY(-30px)}to{opacity:1;transform:translateY(0)}}
h1{font-size:clamp(2.5rem,8vw,4rem);font-weight:800;background:linear-gradient(135deg,#fff 0%,#aaa 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:15px;letter-spacing:-2px}
.badge{background:linear-gradient(90deg,var(--primary),var(--secondary));padding:8px 18px;border-radius:40px;font-size:.85rem;font-weight:700;display:inline-block;margin-bottom:25px;text-transform:uppercase;letter-spacing:1px;box-shadow:0 10px 30px rgba(255,61,113,0.3)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:30px;margin-top:20px}
.card{background:var(--card-bg);border:1px solid var(--glass);border-radius:28px;padding:35px;transition:all .4s cubic-bezier(.175,.885,.32,1.275);backdrop-filter:blur(12px);display:flex;flex-direction:column}
@media(hover:hover){.card:hover{transform:translateY(-12px) scale(1.02);border-color:rgba(255,255,255,.2);box-shadow:0 30px 60px rgba(0,0,0,.5)}}
.card-title{font-size:1.5rem;font-weight:700;margin-bottom:18px;display:flex;align-items:center;gap:12px}
.card-title i{width:32px;height:32px;background:rgba(255,255,255,0.05);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1rem;color:var(--accent);font-style:normal}
.card-desc{color:#9ea3ac;font-size:1rem;line-height:1.6;margin-bottom:25px;flex-grow:1}
.endpoint{font-family:'JetBrains Mono',monospace;background:rgba(0,0,0,.4);padding:14px;border-radius:14px;font-size:.8rem;color:var(--accent);border:1px solid rgba(0,242,255,.15);margin-bottom:25px;word-break:break-all;position:relative}
.endpoint::after{content:'GET';position:absolute;right:14px;top:14px;font-size:.65rem;font-weight:800;color:rgba(255,255,255,.3)}
.btn{display:flex;align-items:center;justify-content:center;padding:16px;background:#fff;color:#000;text-decoration:none;border-radius:16px;font-weight:700;font-size:.95rem;transition:all .3s}
.btn:hover{background:var(--primary);color:#fff;transform:translateY(-2px);box-shadow:0 10px 25px rgba(255,61,113,.4)}
footer{text-align:center;padding:80px 0 40px;animation:fadeIn 2s ease}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.dev-tag{font-weight:800;color:#666;letter-spacing:3px;text-transform:uppercase;font-size:.75rem;border:1px solid #222;padding:12px 30px;border-radius:50px;display:inline-block;background:rgba(255,255,255,.01);transition:all .3s;text-decoration:none}
.dev-tag:hover{color:var(--text);border-color:var(--primary);letter-spacing:5px}
.tag-new{background:var(--accent);color:#000;font-size:.6rem;font-weight:800;padding:3px 8px;border-radius:6px;letter-spacing:1px;margin-left:6px;vertical-align:middle}
.footer-links{margin-top:16px;display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.footer-links a{color:#667;text-decoration:none;font-size:.85rem;font-weight:500;transition:color .2s}
.footer-links a:hover{color:var(--primary)}
@media(max-width:480px){.container{padding:40px 16px}.card{padding:25px}h1{margin-bottom:10px}}
</style>
</head>
<body>
<div class="container">
<header>
<div class="badge">v2.9.1 &middot; Release Updates</div>
<h1>MovieBox Pro</h1>
<p style="color:#667;font-size:1.25rem;font-weight:300">State-of-the-Art Pure API Architecture</p>
</header>
<div class="grid">
<div class="card"><div class="card-title"><i>⚡</i> Providers<span class="tag-new">v2.7</span></div><p class="card-desc">Live health of every mirror. Circuit breaker state, latency, success/failure counts.</p><div class="endpoint">/providers</div><a href="/providers" target="_blank" class="btn">View</a></div>
<div class="card"><div class="card-title"><i>📇</i> Catalog</div><p class="card-desc">Indexed catalog. Type/sort/search filters.</p><div class="endpoint">/catalog?type=movie</div><a href="/catalog" target="_blank" class="btn">Open</a></div>
<div class="card"><div class="card-title"><i>📊</i> Stats</div><p class="card-desc">Counts, walk state, keyword telemetry.</p><div class="endpoint">/catalog/stats</div><a href="/catalog/stats" target="_blank" class="btn">View</a></div>
<div class="card"><div class="card-title"><i>🏠</i> Home</div><p class="card-desc">Home feed.</p><div class="endpoint">/home</div><a href="/home" target="_blank" class="btn">Open</a></div>
<div class="card"><div class="card-title"><i>🧩</i> Sections</div><p class="card-desc">List home sections.</p><div class="endpoint">/sections</div><a href="/sections" target="_blank" class="btn">List</a></div>
<div class="card"><div class="card-title"><i>🗂️</i> Browse</div><p class="card-desc">Any section by name.</p><div class="endpoint">/browse/Cinema</div><a href="/browse/Cinema" target="_blank" class="btn">Open</a></div>
<div class="card"><div class="card-title"><i>🎬</i> Movies</div><p class="card-desc">Home fallback catalog.</p><div class="endpoint">/movies</div><a href="/movies" target="_blank" class="btn">Open</a></div>
<div class="card"><div class="card-title"><i>📺</i> TV</div><p class="card-desc">Home fallback catalog.</p><div class="endpoint">/tv-series</div><a href="/tv-series" target="_blank" class="btn">Open</a></div>
<div class="card"><div class="card-title"><i>🌸</i> Animation</div><p class="card-desc">Home fallback catalog.</p><div class="endpoint">/animation</div><a href="/animation" target="_blank" class="btn">Open</a></div>
<div class="card"><div class="card-title"><i>🔍</i> Search</div><p class="card-desc">Full-text search.</p><div class="endpoint">/search?q=matrix</div><a href="/search?q=matrix" target="_blank" class="btn">Search</a></div>
<div class="card"><div class="card-title"><i>💡</i> Suggest</div><p class="card-desc">Typeahead. <code>?enrich=true</code>.</p><div class="endpoint">/search/suggest?q=break</div><a href="/search/suggest?q=break" target="_blank" class="btn">Try</a></div>
<div class="card"><div class="card-title"><i>🆔</i> Detail</div><p class="card-desc">Full metadata.</p><div class="endpoint">/detail/{slug}</div><a href="/detail/attack-on-titan-hindi-kGWQOIx0d4" target="_blank" class="btn">Fetch</a></div>
<div class="card"><div class="card-title"><i>🎥</i> Stream</div><p class="card-desc">MP4 sources + manifests.</p><div class="endpoint">/api/stream/{sid}</div><a href="/api/stream/56988683026712168?detail_path=attack-on-titan-hindi-kGWQOIx0d4" target="_blank" class="btn">Get</a></div>
<div class="card"><div class="card-title"><i>📥</i> Proxy</div><p class="card-desc">Range-aware MP4 passthrough.</p><div class="endpoint">/api/stream/{sid}/proxy</div><a href="/api/stream/56988683026712168/proxy?detail_path=attack-on-titan-hindi-kGWQOIx0d4&res=best" target="_blank" class="btn">Stream</a></div>
<div class="card"><div class="card-title"><i>📄</i> VTT</div><p class="card-desc">SRT → WebVTT inline.</p><div class="endpoint">/api/stream/{sid}/subtitles/{lang}</div><a href="/api/stream/6207982430134357800/subtitles/en?detail_path=breaking-bad-ej6Bp0MCAo7" target="_blank" class="btn">Get</a></div>
<div class="card"><div class="card-title"><i>❤️</i> Health</div><p class="card-desc">Liveness + per-provider state.</p><div class="endpoint">/health</div><a href="/health" target="_blank" class="btn">Check</a></div>
</div>
<footer>
<a href="https://github.com/faisaljs" target="_blank" class="dev-tag">Developer: Faisal</a>
<div class="footer-links">
<a href="https://github.com/faisaljs/Moviebox-API" target="_blank">GitHub Repo</a>
<a href="https://github.com/faisaljs" target="_blank">@faisaljs</a>
<a href="/app" target="_blank">Frontend</a>
<a href="/docs" target="_blank">API Docs</a>
</div>
</footer>
</div>
</body>
</html>"""
