#!/usr/bin/env python3
"""HTML dashboard for the session log.

Renders the event stream as a readable *flow* -- one turn per user prompt,
with reasoning, tool calls and the result each call came back with nested
under it -- plus the aggregate views (share bar, per-minute volume, per-source
tiles) that make the shape of a session legible at a glance.

Styling follows the Lexsus / Zhilo Labs system: a paper ramp, three type
voices (Instrument Serif display, Instrument Sans body, JetBrains Mono meta),
hairline borders, no shadows, and no decorative animation -- this is a
dashboard, so things appear where they are and stay there.

The state payload is transcript text, i.e. arbitrary. `render()` is the only
place that stitches it into the document and it escapes accordingly.
"""

CSS = r"""
*,*::before,*::after{box-sizing:border-box}

:root{
  /* Every token below is a settings value with a default that matches the
     design system. applyCfg() writes the ones a setting declares (`cssvar` +
     `unit` in trajectory.py's CONFIG_SPEC) onto this element, so a knob and
     the thing it moves are one line apart rather than two lists that drift. */
  --bg:#F7F5F2;
  --bg-2:#FFFFFF;
  --bg-3:#EDE9E3;
  --fg:#1A1917;
  --muted:#6B6660;
  --faint:#9A948C;
  /* hairlines are a colour *and* an alpha, so "hairline strength" is one
     number rather than a second palette to keep in step */
  --hair-c:#E2DED7;
  --hair2-c:#EEEAE4;
  --hair-a:100;
  --hair:color-mix(in oklab, var(--hair-c) calc(var(--hair-a) * 1%), transparent);
  --hair-2:color-mix(in oklab, var(--hair2-c) calc(var(--hair-a) * 1%), transparent);
  --wash:#F2EFEA;
  --brand:#2F6F4E;
  --tint:13%;
  --fs:100;
  --radius:4px;
  --pad:8px;
  --gap:14px;
  --dot:7px;
  --rail:240px;
  --insp:600px;
  --trh:26px;
  --clamp:2;
  --indent:18px;
  --spark:46px;
  --wf-h:11px;
  --wf-lw:58px;
  --wf-gap:10px;
  --wf-input:#2E6FB8;
  --wf-model:#8A4FBF;
  --wf-tool:#2F7F5F;
  --src-prompt:#B4642A;
  --src-text:#8A4FBF;
  --src-reasoning:#7A4FA8;
  --src-toolcall:#2E6FB8;
  --src-toolresult:#2F7F5F;
  --src-inject:#8A6A16;
  --src-system:#4A7A8C;
  --src-other:#6B6660;
  --sans:"Instrument Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --serif:"Instrument Serif",Georgia,"Times New Roman",serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}

/* The dark stock. Same structure, inverted ramp -- set by the palette knob. */
body[data-theme=ink]{
  --bg:#14161A; --bg-2:#1A1D22; --bg-3:#22262C;
  --fg:#E8E6E1; --muted:#9C9791; --faint:#6E6A64;
  --hair-c:#2E333A; --hair2-c:#242930; --wash:#1F2329;
}
body[data-theme=ink] .noise{mix-blend-mode:screen;opacity:.04}

/* Interface scale. The design is set in px rather than rem, so scaling the
   root font size would move nothing -- `zoom` on the body is the honest
   implementation: type and spacing grow together, and fixed panels follow. */
body{zoom:calc(var(--fs) / 100)}

/* --- appearance settings ------------------------------------------------
   Each of these is one `attr` in CONFIG_SPEC: the knob sets
   `document.body.dataset.<name>` and the rule below is the whole effect.
   No JavaScript branch, and nothing to keep in sync. */
body[data-grain=false] .noise{display:none}
body[data-serif=false]{--serif:var(--sans)}
body[data-wide=false] .shell,
body[data-wide=false] .set{max-width:1180px;margin-left:auto;margin-right:auto}
body[data-stickynav=false] .nav{position:static}
body[data-shadow=true] .panel,body[data-shadow=true] .tile,
body[data-shadow=true] .turn,body[data-shadow=true] .dd-p,
body[data-shadow=true] .cs-p{box-shadow:0 2px 10px rgba(26,25,23,.07)}
body[data-uplat=false] .label,body[data-uplat=false] .pill,
body[data-uplat=false] .badge,body[data-uplat=false] th,
body[data-uplat=false] .wf-l,body[data-uplat=false] .ik,
body[data-uplat=false] .cfg-badge,body[data-uplat=false] .set-cat,
body[data-uplat=false] .hint,body[data-uplat=false] .dd-h,
body[data-uplat=false] .ibadge,body[data-uplat=false] .crumb,
body[data-uplat=false] .smeta .k{text-transform:none;letter-spacing:.02em}
body[data-zebra=true] tr.ev:nth-child(even){background:var(--wash)}
body[data-motion=false] .step.flash,body[data-motion=false] tr.flash{
  animation:none;background:transparent}
/* One knob whose whole effect is hiding an element the markup always emits.
   (The waterfall's lane labels are not done this way -- they own a grid column,
   so renderWaterfall() drops both the column and the label together.) */
body[data-flowmeta=false] .step-m{display:none}

html{-webkit-text-size-adjust:100%;scrollbar-color:var(--bg-3) transparent}
body{
  margin:0;background:var(--bg);color:var(--fg);
  font-family:var(--sans);font-size:15px;line-height:1.5;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
  overflow-x:hidden;
}
a{color:inherit;text-decoration:none}
button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}

/* film grain, per the design system. On paper it reads as a faint tooth in the
   stock rather than speckle, so it is mixed lighter and kept monochrome. */
.noise{
  position:fixed;inset:0;z-index:80;pointer-events:none;opacity:.022;
  mix-blend-mode:multiply;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)'/%3E%3C/svg%3E");
}

/* --- nav: no transitions, no scroll-triggered state ---------------------- */
.nav{position:sticky;top:0;z-index:60;border-bottom:1px solid var(--hair);
  background:color-mix(in oklab, var(--bg) 92%, transparent);
  backdrop-filter:blur(10px)}
.nav-inner{padding:10px 22px;
  display:flex;align-items:center;gap:8px 14px;flex-wrap:wrap}
.spacer{flex:1 1 auto}
.logo{display:inline-flex;align-items:center;gap:8px;font-family:var(--serif);
  font-size:19px;letter-spacing:-.01em;white-space:nowrap}
.logo .dot{width:8px;height:8px;border-radius:999px;background:var(--brand);
  display:inline-block}
.logo sup{font-family:var(--mono);font-size:8px;color:var(--faint);
  letter-spacing:.1em;margin-left:1px}

.pill{border:1px solid var(--hair);border-radius:999px;padding:5px 12px;
  font-family:var(--mono);font-size:10px;text-transform:uppercase;
  letter-spacing:.14em;color:var(--muted);white-space:nowrap}
.pill:hover{border-color:color-mix(in oklab, var(--fg) 26%, transparent);color:var(--fg)}
.pill[aria-pressed=true]{color:var(--fg);border-color:var(--brand);
  background:color-mix(in oklab, var(--brand) var(--tint), transparent)}
.pill:disabled{cursor:default;opacity:.6}
.pill.stop{color:#B3261E;
  border-color:color-mix(in oklab, #B3261E 34%, transparent)}
.pill.stop:hover{color:#8C1D18;
  border-color:color-mix(in oklab, #8C1D18 60%, transparent)}
.seg{display:inline-flex;gap:6px}

/* --- dropdowns ---------------------------------------------------------- */
/* The nav used to carry one pill per source category; seven of them, plus any
   filter chips, pushed Settings and Stop off a laptop screen. One control that
   opens a list scales where a row of pills does not. */
.dd{position:relative;display:inline-block}
.dd-b .caret{font-size:9px;opacity:.65}
.dd-p{position:absolute;top:calc(100% + 7px);right:0;z-index:70;
  min-width:250px;max-width:min(340px,92vw);max-height:min(64vh,460px);
  overflow:auto;overscroll-behavior:contain;
  background:var(--bg-2);border:1px solid var(--hair);
  border-radius:var(--radius);padding:6px;
  box-shadow:0 10px 26px rgba(26,25,23,.12)}
.dd-p[hidden]{display:none}
.dd-h{font-family:var(--mono);font-size:9px;text-transform:uppercase;
  letter-spacing:.16em;color:var(--faint);padding:8px 8px 4px;margin:0}
.dd-i{display:flex;align-items:center;gap:9px;width:100%;text-align:left;
  padding:6px 8px;border-radius:3px;font-family:var(--mono);font-size:11px;
  color:var(--muted);cursor:pointer;min-width:0}
.dd-i:hover{background:var(--wash);color:var(--fg)}
.dd-i[aria-pressed=true]{color:var(--fg);background:var(--wash)}
.dd-i .sw{width:var(--dot);height:var(--dot);border-radius:999px;flex:0 0 auto;
  border:1px solid var(--hair)}
.dd-i .n{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.dd-i .c{color:var(--faint);font-size:10px;flex:0 0 auto}
.dd-i .x{color:var(--faint);font-size:12px;line-height:1;padding:0 2px;
  flex:0 0 auto}
.dd-i .x:hover{color:var(--fg)}
.dd-sep{height:1px;background:var(--hair-2);margin:5px 6px}
.dd-f{display:flex;gap:6px;padding:7px 6px 2px;margin-top:4px;
  border-top:1px solid var(--hair-2)}
.dd-in{width:100%;background:var(--bg);border:1px solid var(--hair);
  border-radius:3px;color:var(--fg);font-family:var(--mono);font-size:11px;
  padding:6px 8px}
.dd-in:focus{outline:none;border-color:color-mix(in oklab, var(--brand) 55%, transparent)}

.live{display:inline-flex;align-items:center;gap:7px;font-family:var(--mono);
  font-size:10px;text-transform:uppercase;letter-spacing:.14em;color:var(--faint);
  border:1px solid var(--hair);border-radius:999px;padding:4px 11px;white-space:nowrap}
.live .dot{width:6px;height:6px;border-radius:999px;background:currentColor;
  opacity:.4;display:inline-block}
.live.on{color:var(--brand);border-color:color-mix(in oklab, var(--brand) 45%, transparent)}
.live.on .dot{opacity:1}
/* A clock in the nav is the one honest liveness signal on a page that polls:
   the content may be a minute stale, but the tab is definitely up. */
.clock{font-family:var(--mono);font-size:10px;color:var(--faint);
  letter-spacing:.06em;font-variant-numeric:tabular-nums;white-space:nowrap}
.clock:empty{display:none}

/* --- shell -------------------------------------------------------------- */
/* Full-bleed: the page is a workspace, not a column. A capped width left a
   third of a wide monitor empty while the event stream wrapped. */
.shell{padding:22px 22px 72px;
  display:grid;grid-template-columns:minmax(0,var(--rail)) minmax(0,1fr);
  gap:26px;grid-template-areas:"side main";align-items:start}
.side{grid-area:side;min-width:0}
.main{grid-area:main;min-width:0}

.crumb{font-family:var(--mono);font-size:10px;text-transform:uppercase;
  letter-spacing:.2em;color:var(--faint);margin:0 0 8px;word-break:break-all}
h1{font-family:var(--serif);font-weight:400;font-size:clamp(27px,4.2vw,42px);
  line-height:1.05;margin:0 0 10px;letter-spacing:-.01em}
.smeta{display:flex;flex-wrap:wrap;gap:6px 16px;font-family:var(--mono);
  font-size:11px;color:var(--muted);margin:0 0 20px}
.smeta b{font-weight:400;color:var(--fg)}

/* --- panels ------------------------------------------------------------- */
.panel{border:1px solid var(--hair);border-radius:var(--radius);
  background:var(--bg-2);margin-bottom:var(--gap);
  min-width:0}
.panel-h{display:flex;align-items:center;justify-content:space-between;
  gap:10px 14px;padding:11px 14px;border-bottom:1px solid var(--hair-2);
  flex-wrap:wrap}
.panel-b{padding:14px}
.panel-h .hint{margin-left:auto}
.label{font-family:var(--mono);font-size:10px;text-transform:uppercase;
  letter-spacing:.16em;color:var(--faint);margin:0}
.label b{font-weight:400;color:var(--muted)}

/* share bar */
.share{display:flex;height:11px;border-radius:999px;overflow:hidden;
  border:1px solid var(--hair-2);background:var(--bg)}
.share i{display:block;height:100%}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:13px}
.legend span{display:inline-flex;align-items:center;gap:7px;
  font-family:var(--mono);font-size:11px;color:var(--muted);min-width:0}
.legend .dot{width:var(--dot);height:var(--dot);border-radius:999px;flex:0 0 auto}
.legend em{font-style:normal;color:var(--faint)}
.legend .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:16ch}

/* volume per minute */
.sparkbox{margin-top:16px;padding-top:14px;border-top:1px solid var(--hair-2)}
.spark{display:block;width:100%;height:var(--spark)}
.spark-meta{font-family:var(--mono);font-size:10px;color:var(--faint);
  margin:8px 0 0;letter-spacing:.06em}

/* tiles */
.tiles{display:grid;gap:10px;
  grid-template-columns:repeat(auto-fill,minmax(158px,1fr))}
.tile{border:1px solid var(--hair);border-radius:var(--radius);padding:12px;
  background:var(--bg-2);min-width:0}
.tile .src{display:flex;align-items:center;gap:7px;font-family:var(--mono);
  font-size:11px;color:var(--muted);margin:0 0 7px;min-width:0}
.tile .src .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tile .src .dot{width:var(--dot);height:var(--dot);border-radius:999px;
  flex:0 0 auto}
.tile .n{font-family:var(--serif);font-size:25px;line-height:1;margin:0}
.tile .sub{font-family:var(--mono);font-size:10px;color:var(--faint);
  margin:7px 0 0}
.bar{height:3px;border-radius:999px;background:var(--hair-2);margin-top:10px;
  overflow:hidden}
.bar i{display:block;height:100%}

/* billed strip */
.billed{display:flex;flex-wrap:wrap;gap:10px 26px;font-family:var(--mono);
  font-size:11px;color:var(--fg);font-variant-numeric:tabular-nums}
.billed div{min-width:0}
.billed .k{display:block;font-size:9px;text-transform:uppercase;
  letter-spacing:.16em;color:var(--faint);margin-bottom:3px}

/* --- sidebar ------------------------------------------------------------ */
.side-head{display:flex;align-items:baseline;justify-content:space-between;
  gap:8px;margin-bottom:9px}
.input{width:100%;background:var(--bg-2);border:1px solid var(--hair);
  border-radius:var(--radius);color:var(--fg);font-family:var(--mono);
  font-size:11px;padding:7px 10px;margin-bottom:9px}
.input::placeholder{color:var(--faint)}
.input:focus{outline:none;border-color:color-mix(in oklab, var(--brand) 55%, transparent)}
.sess{list-style:none;margin:0;padding:0;max-height:64vh;overflow:auto}
.sess button{display:block;width:100%;text-align:left;padding:var(--pad) 10px;
  border-radius:var(--radius);border:1px solid transparent;min-width:0}
.sess button:hover{background:var(--wash)}
.sess button[aria-current=true]{border-color:var(--hair);
  background:color-mix(in oklab, var(--brand) 8%, transparent)}
.sid{display:flex;align-items:center;gap:7px;font-family:var(--mono);
  font-size:11.5px;color:var(--fg)}
.sid .dot{width:6px;height:6px;border-radius:999px;background:var(--brand);
  flex:0 0 auto}
.proj{display:block;font-size:11px;color:var(--muted);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.meta{display:flex;gap:10px;font-family:var(--mono);font-size:9.5px;
  color:var(--faint);margin-top:3px}

/* --- flow --------------------------------------------------------------- */
.turn{border:1px solid var(--hair);border-radius:var(--radius);
  background:var(--bg-2);
  margin-bottom:12px;overflow:hidden}
.turn-h{display:flex;align-items:center;gap:8px 12px;padding:10px 14px;
  border-bottom:1px solid var(--hair-2);flex-wrap:wrap}
.turn-n{font-family:var(--serif);font-size:15px}
.turn-m{font-family:var(--mono);font-size:10.5px;color:var(--faint);
  letter-spacing:.06em}
.badge{font-family:var(--mono);font-size:9.5px;text-transform:uppercase;
  letter-spacing:.13em;padding:2px 8px;border-radius:999px;
  border:1px solid var(--hair);color:var(--muted);white-space:nowrap}
.badge.tool{color:var(--fg);border-color:color-mix(in oklab, var(--fg) 24%, transparent)}
.prompt{margin:0;padding:11px 14px;border-bottom:1px solid var(--hair-2);
  font-size:14px;background:color-mix(in oklab, var(--brand) 6%, transparent);
  white-space:pre-wrap;word-break:break-word}
.steps{list-style:none;margin:0;padding:0}
.step{position:relative;padding:calc(var(--pad) + 2px) 14px
  calc(var(--pad) + 2px) 30px;cursor:pointer;
  border-top:1px solid var(--hair-2);min-width:0}
.steps > .step:first-child{border-top:0}
.step:hover{background:var(--wash)}
.step > .node{position:absolute;left:15px;top:16px;width:8px;height:8px;
  border-radius:999px;border:2px solid var(--bg-2)}
.step-h{display:flex;align-items:center;gap:8px 12px;flex-wrap:wrap;
  margin-bottom:5px}
.step-m{font-family:var(--mono);font-size:10px;color:var(--faint);
  letter-spacing:.06em}
.step-b{min-width:0}
.step.sub{margin:8px 0 0 var(--indent);padding:9px 12px;
  border:1px solid var(--hair-2);
  border-left:1px solid var(--brand);border-radius:0 var(--radius) var(--radius) 0;
  background:var(--wash)}
.step.sub > .step-h{margin-bottom:4px}

.txt{margin:0;font-size:13.5px;color:var(--muted);white-space:pre-wrap;
  word-break:break-word;overflow-wrap:anywhere}
.step.sub .txt,.txt.mono{font-family:var(--mono);font-size:11.5px;line-height:1.65}
.clamp{display:-webkit-box;-webkit-line-clamp:var(--clamp);
  -webkit-box-orient:vertical;
  overflow:hidden}
.step.open > .step-b .clamp,.step.open > .step-b .txt{display:block;
  -webkit-line-clamp:unset;overflow:visible}
.step.open > .step-b .txt{}
.txt.full{-webkit-line-clamp:unset;display:block}

/* the collapsed tool-call line reads like a shell command */
.cmd{margin:0;font-family:var(--mono);font-size:11.5px;line-height:1.6;
  color:var(--fg);white-space:pre-wrap;word-break:break-word;
  overflow-wrap:anywhere}

.json{margin:0;font-family:var(--mono);font-size:11.5px;line-height:1.65;
  white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere;
  color:var(--muted)}
.jk{color:#1F6FB2}
.js{color:#2F7A4F}
.jn{color:#9A5B18}
.kb{color:#8A3FA8}

.hint{font-family:var(--mono);font-size:9.5px;color:var(--faint);
  letter-spacing:.12em;text-transform:uppercase}
.empty{padding:26px 14px;text-align:center;font-family:var(--mono);
  font-size:11px;color:var(--faint)}

@keyframes flash{from{background:color-mix(in oklab, var(--brand) var(--tint), transparent)}
  to{background:transparent}}
.step.flash{animation:flash 1.5s ease-out 1}

.flow-more{padding:14px;text-align:center;border-bottom:1px solid var(--hair-2)}
.turn-cut{padding:9px 14px;border-bottom:1px solid var(--hair-2);margin:0;
  text-align:center}

/* --- status strip: the status line, laid out for the page ---------------- */
.status{display:flex;flex-wrap:wrap;align-items:center;gap:8px 0;
  border:1px solid var(--hair);border-radius:var(--radius);
  background:var(--bg-2);
  padding:10px 14px;margin:0 0 16px;font-family:var(--mono);font-size:11px;
  font-variant-numeric:tabular-nums;overflow:hidden}
.status .seg{display:inline-flex;align-items:center;gap:7px;
  padding:0 12px;border-right:1px solid var(--hair-2);white-space:nowrap}
.status .seg:last-child{border-right:0}
.status .k{color:var(--faint);font-size:9px;text-transform:uppercase;
  letter-spacing:.14em}
.status .model{color:var(--fg);font-weight:500}
.status .proj{color:var(--faint)}
.status .cbar{width:96px;height:7px;border-radius:999px;background:var(--hair-2);
  overflow:hidden;display:inline-block}
.status .cbar i{display:block;height:100%}
.status .pct{font-weight:500}
.status .up{color:#2E6FB8}
.status .down{color:#8A4FBF}
.status .sum{color:var(--brand)}
.status .cost{color:#8A6A16}
.status .miss{color:var(--faint)}

/* --- waterfall: per-turn Input / Model / Tools spans ---------------------
   A Gantt of one turn: the lane bars are measured gaps between real records,
   so a 180s Bash command and a 20ms Read look as different as they are. */
.wf{border-bottom:1px solid var(--hair-2);padding:var(--wf-gap) 0}
.wf:first-child{padding-top:2px}
.wf:last-child{border-bottom:0;padding-bottom:2px}
.wf-h{display:flex;flex-wrap:wrap;gap:5px 13px;align-items:baseline;
  margin-bottom:8px}
.wf-h .badge{font-family:var(--mono);font-size:9.5px;text-transform:uppercase;
  letter-spacing:.14em;color:var(--fg);border:1px solid var(--hair);
  border-radius:999px;padding:2px 8px}
.wf-h .turn-m{font-family:var(--mono);font-size:10px;color:var(--faint)}
.wf-h .dur{color:var(--muted)}
.wf-row{display:grid;grid-template-columns:var(--wf-lw) minmax(0,1fr);gap:9px;
  align-items:center;padding:1.5px 0}
.wf-l{font-family:var(--mono);font-size:9.5px;text-transform:uppercase;
  letter-spacing:.1em;color:var(--muted);text-align:right}
.wf-t{position:relative;height:var(--wf-h);background:var(--wash);
  border-radius:2px}
.wfseg{position:absolute;top:0;height:100%;min-width:1.5px;border-radius:1.5px;
  cursor:default}
.wfseg:hover{outline:1px solid var(--fg);outline-offset:0}
.wfseg.input{background:var(--wf-input)}
.wfseg.model{background:var(--wf-model)}
.wfseg.tool{background:var(--wf-tool)}
.wf-axis{display:grid;grid-template-columns:var(--wf-lw) minmax(0,1fr);gap:9px;
  margin-top:5px}
.wf-ticks{position:relative;height:11px;border-top:1px solid var(--hair-2)}
.wf-ticks span{position:absolute;top:3px;transform:translateX(-50%);
  font-family:var(--mono);font-size:8.5px;color:var(--faint);white-space:nowrap}
.wf-legend{display:flex;flex-wrap:wrap;gap:8px 16px;margin-bottom:10px}
.wf-legend span{display:inline-flex;align-items:center;gap:6px;
  font-family:var(--mono);font-size:10px;color:var(--muted)}
.wf-legend i{width:9px;height:9px;border-radius:2px;display:inline-block}
.wf-legend em{font-style:normal;color:var(--faint)}

/* --- tracking options --------------------------------------------------- */
.opts{display:grid;gap:12px 16px;
  grid-template-columns:repeat(auto-fit,minmax(190px,1fr));align-items:end}
.fld{display:block;min-width:0}
.fld .label{display:block;margin-bottom:5px}
.chk{display:flex;align-items:center;gap:8px;font-family:var(--mono);
  font-size:11px;color:var(--muted);cursor:pointer;padding-bottom:2px}
.chk input{accent-color:var(--brand);width:14px;height:14px;margin:0}
.scount{margin:10px 2px 0}

/* --- inspect: the detail sidebar a trace opens --------------------------- */
/* Reading a bar chart tells you where the time went; it cannot tell you what
   the tool was called with. The panel is the other half of the trace. */
.inspect{position:fixed;top:0;right:0;bottom:0;z-index:85;
  width:min(var(--insp),100vw);background:var(--bg-2);
  border-left:1px solid var(--hair);display:flex;flex-direction:column}
.inspect[hidden]{display:none}
.inspect-h{display:flex;align-items:center;gap:8px;padding:11px 14px;
  border-bottom:1px solid var(--hair);flex:0 0 auto}
.inspect-h .label{color:var(--fg)}
.inspect-b{overflow:auto;padding:14px 16px 40px;flex:1 1 auto;min-width:0}
.if{display:grid;grid-template-columns:104px minmax(0,1fr);gap:6px 12px;
  padding:5px 0;border-bottom:1px solid var(--hair-2);align-items:baseline}
.if:last-child{border-bottom:0}
.ik{font-family:var(--mono);font-size:9.5px;text-transform:uppercase;
  letter-spacing:.14em;color:var(--faint)}
.iv{font-size:12.5px;color:var(--fg);overflow-wrap:anywhere;min-width:0}
.iv.mono{font-family:var(--mono);font-size:11.5px}
.iscet{margin-top:16px}
.iscet > .label{display:block;margin-bottom:6px}
.ibox{border:1px solid var(--hair);border-radius:var(--radius);
  padding:10px 12px;background:var(--bg)}
.inspect .json{color:var(--muted)}
.ibadge{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);
  font-size:10px;text-transform:uppercase;letter-spacing:.12em;
  border:1px solid var(--hair);border-radius:999px;padding:2px 9px}
.ibadge .dot{width:7px;height:7px;border-radius:999px}

/* Hover tooltip. Native `title` waits a second, cannot be styled, and is
   unavailable on the touch devices this page is opened on. */
.tip{position:fixed;z-index:95;pointer-events:none;max-width:min(340px,86vw);
  background:var(--fg);color:var(--bg);font-family:var(--mono);font-size:10.5px;
  line-height:1.55;padding:7px 10px;border-radius:4px;
  box-shadow:0 6px 20px rgba(26,25,23,.24)}
.tip[hidden]{display:none}
.tip .r{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tip .k{opacity:.6}
.tip .hd{font-weight:500;display:block;margin-bottom:2px}

/* --- settings: a page of its own --------------------------------------- */
/* The panel used to be a drawer over the dashboard. With a hundred-odd knobs
   across sixteen groups that became a scroll inside a scroll, and the thing
   the knobs are supposed to *move* -- the page -- was hidden behind it. */
.set{display:grid;grid-template-columns:minmax(0,calc(var(--rail) + 40px)) minmax(0,1fr);
  gap:0;min-height:calc(100vh - 53px);align-items:start}
.set[hidden]{display:none}
.set-rail{border-right:1px solid var(--hair);padding:18px 16px 60px;
  position:sticky;top:53px;max-height:calc(100vh - 53px);overflow:auto}
.set-body{padding:18px 26px 80px;min-width:0}
.set-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  margin-bottom:10px}
.set-head h2{font-family:var(--serif);font-weight:400;font-size:26px;margin:0;
  letter-spacing:-.01em}
.set-cat{display:flex;align-items:center;gap:8px;width:100%;text-align:left;
  padding:6px 9px;border-radius:var(--radius);font-family:var(--mono);
  font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.set-cat:hover{background:var(--wash);color:var(--fg)}
.set-cat[aria-current=true]{color:var(--fg);
  background:color-mix(in oklab, var(--brand) 9%, transparent)}
.set-cat .n{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.set-cat .c{color:var(--faint);font-size:10px}
.set-cat .c.hit{color:var(--brand)}
.set-g{margin:0 0 26px;scroll-margin-top:66px}
.set-g > h3{font-family:var(--serif);font-weight:400;font-size:19px;margin:0;
  padding-bottom:7px;border-bottom:1px solid var(--hair)}
.set-row{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:8px 20px;
  padding:11px 0;border-bottom:1px solid var(--hair-2);align-items:start}
.set-row:last-child{border-bottom:0}
.set-l{min-width:0}
.set-l .t{font-size:13px;color:var(--fg)}
.set-l .k{font-family:var(--mono);font-size:9.5px;color:var(--faint);
  margin-left:7px}
.set-l .h{font-size:11.5px;color:var(--faint);line-height:1.45;margin-top:2px}
.set-row.changed .t{color:var(--brand)}
.set-row.changed .t::after{content:" •";color:var(--brand)}
.set-c{border:0;padding:0;margin:0;min-width:0;display:flex;
  align-items:center;gap:8px;justify-content:flex-end;flex-wrap:wrap}
.set-empty{font-family:var(--mono);font-size:11.5px;color:var(--faint);
  padding:30px 0}
.set-note{font-family:var(--mono);font-size:10px;color:var(--faint);
  margin:0 0 14px;overflow-wrap:anywhere}
.set-c .input{margin-bottom:0}

/* --- extract: choices on the left, the actual bytes on the right -------- */
/* A preview next to the controls, because "what does CSV look like with full
   text on" is a question you answer by looking, not by exporting twice. */
.ex{display:grid;grid-template-columns:minmax(0,460px) minmax(0,1fr);
  min-height:calc(100vh - 53px);align-items:start}
.ex[hidden]{display:none}
.ex-l{padding:18px 24px 60px;min-width:0;border-right:1px solid var(--hair)}
.ex-r{display:flex;flex-direction:column;min-width:0;height:calc(100vh - 53px);
  position:sticky;top:53px}
.ex-bar{display:flex;align-items:center;gap:10px;padding:14px 18px;
  border-bottom:1px solid var(--hair)}
.ex-bar .label{color:var(--fg)}
.ex-size{font-family:var(--mono);font-size:10px;color:var(--faint);
  white-space:nowrap}
.ex-prev{flex:1 1 auto;overflow:auto;margin:0;padding:14px 18px 40px;
  font-family:var(--mono);font-size:11px;line-height:1.6;color:var(--muted);
  white-space:pre;tab-size:2}
.ex-prev:focus-visible{outline:2px solid var(--brand);outline-offset:-2px}
.ex-empty{padding:22px 18px;font-family:var(--mono);font-size:11.5px;
  color:var(--faint)}
.pill.primary{background:var(--brand);border-color:var(--brand);color:#fff}
.pill.primary:hover{background:color-mix(in oklab, var(--brand) 84%, #000);
  border-color:transparent;color:#fff}
.cfg-g{margin-top:18px}
.cfg-g > .label{display:block;margin-bottom:2px;color:var(--muted)}
.cfg-row{padding:9px 0;border-bottom:1px solid var(--hair-2)}
.cfg-row:last-child{border-bottom:0}
.cfg-top{display:flex;align-items:center;gap:8px}
.cfg-top .lbl{font-size:12.5px;color:var(--fg);flex:1 1 auto;min-width:0}
.cfg-top .ctl{flex:0 0 auto;display:flex;align-items:center;gap:6px}
.cfg-h{font-size:11px;color:var(--faint);line-height:1.45;margin-top:2px}
.cfg-row.changed .lbl{color:var(--brand)}
.cfg-row.changed .lbl::after{content:" •";color:var(--brand)}
.cfg-undo{font-family:var(--mono);font-size:11px;color:var(--faint);
  padding:1px 5px;border-radius:var(--radius)}
.cfg-undo:hover{color:var(--fg);background:var(--wash)}
.cfg-num{width:88px;text-align:right;padding:5px 7px;font-family:var(--mono);
  font-size:11.5px}
.cfg-num.wide{width:150px;text-align:left}
.cfg-sel{padding:5px 7px;font-family:var(--mono);font-size:11.5px}
.cfg-badge{font-family:var(--mono);font-size:9px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--faint);border:1px solid var(--hair);
  border-radius:999px;padding:1px 6px;flex:0 0 auto}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);
  font-size:11px;color:var(--muted);border:1px solid var(--hair);
  border-radius:999px;padding:3px 9px}
.chip b{font-weight:400;color:var(--fg)}
.chip i{font-style:normal;color:var(--faint)}
.chip button{color:var(--faint);font-size:12px;line-height:1;padding:0}
.chip button:hover{color:var(--fg)}
.chip-add{display:flex;gap:6px;margin-top:9px;flex-wrap:wrap}
.chip-add .input{flex:1 1 90px;min-width:0;padding:5px 7px;font-size:11.5px}
.cfg-empty{font-family:var(--mono);font-size:11px;color:var(--faint);
  margin-top:8px}
.cfg-saved{font-family:var(--mono);font-size:10px;color:var(--brand);
  opacity:0;transition:opacity .18s}
.cfg-saved.on{opacity:1}
/* Density is the coarse preset: it tightens every list at once, which is a
   different job from the row-padding knob (one row's own padding, in px). The
   two overlap by design -- turn density to compact, then row padding up, and
   you get compact lists with roomier record rows. */
body[data-density=compact] .set-row{padding:5px 0}
body[data-density=compact] .set-rail{padding-top:12px}
body[data-density=compact] td{padding:5px 10px}
body[data-density=compact] .step{padding-top:2px;padding-bottom:2px}
body[data-density=compact] .dd-i,
body[data-density=compact] .cs-i,
body[data-density=compact] .sess-opts{padding-top:4px;padding-bottom:4px}
body[data-density=compact] .wf-row{padding:0}
body[data-density=compact] .sess button{padding:4px 8px}
body[data-density=compact] .tile{padding:10px 11px}

/* --- controls ------------------------------------------------------------ */
/* One set of controls, used by both the settings page and Tracking options.
   A native <select> cannot be styled to match anything, opens a system menu
   that looks nothing like the page, and on a laptop shows one option at a
   time -- so the enum control is a button and a list, the same widget as the
   sources menu. */

/* the switch: a two-position control, not a checkbox with a tick */
.sw2{position:relative;width:38px;height:21px;flex:0 0 auto;
  border-radius:999px;border:1px solid var(--hair);background:var(--bg-3)}
.sw2::after{content:"";position:absolute;top:2px;left:2px;width:15px;height:15px;
  border-radius:999px;background:var(--bg-2);border:1px solid var(--hair);
  transition:none}
.sw2[aria-checked=true]{background:var(--brand);border-color:var(--brand)}
.sw2[aria-checked=true]::after{left:auto;right:2px;background:#fff;
  border-color:transparent}
.sw2:focus-visible{outline:2px solid var(--brand);outline-offset:2px}

/* the custom select */
.cs{position:relative;display:inline-block;min-width:0}
.cs-b{display:flex;align-items:center;gap:8px;width:100%;
  background:var(--bg-2);border:1px solid var(--hair);
  border-radius:var(--radius);color:var(--fg);font-family:var(--mono);
  font-size:11.5px;padding:5px 9px;text-align:left;min-width:160px}
.cs-b:hover{border-color:color-mix(in oklab, var(--fg) 26%, transparent)}
.cs-b .v{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.cs-b .caret{font-size:9px;opacity:.65;flex:0 0 auto}
.cs-p{position:absolute;top:calc(100% + 5px);right:0;z-index:75;
  min-width:100%;max-width:min(320px,92vw);max-height:min(58vh,420px);
  overflow:auto;background:var(--bg-2);border:1px solid var(--hair);
  border-radius:var(--radius);padding:5px;
  box-shadow:0 10px 26px rgba(26,25,23,.12)}
.cs-p[hidden]{display:none}
.cs-i{display:flex;align-items:center;gap:8px;width:100%;text-align:left;
  padding:6px 8px;border-radius:3px;font-family:var(--mono);font-size:11.5px;
  color:var(--muted)}
.cs-i:hover{background:var(--wash);color:var(--fg)}
.cs-i .tick{width:11px;flex:0 0 auto;color:var(--brand);font-size:10px}
.cs-i .t{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}

/* number + range, so a bounded knob can be dragged as well as typed */
.numwrap{display:flex;align-items:center;gap:8px;flex:1 1 auto;min-width:0;
  justify-content:flex-end}
.rng{-webkit-appearance:none;appearance:none;width:120px;flex:0 1 120px;
  height:16px;background:none;margin:0}
.rng::-webkit-slider-runnable-track{height:2px;background:var(--hair)}
.rng::-webkit-slider-thumb{-webkit-appearance:none;width:13px;height:13px;
  border-radius:999px;background:var(--brand);margin-top:-5.5px;border:0}
.rng::-moz-range-track{height:2px;background:var(--hair)}
.rng::-moz-range-thumb{width:13px;height:13px;border:0;border-radius:999px;
  background:var(--brand)}

/* colour: the swatch is the picker, the field is the value */
.colwrap{display:flex;align-items:center;gap:8px;flex:1 1 auto;
  justify-content:flex-end;min-width:0}
.swatch{-webkit-appearance:none;appearance:none;width:30px;height:23px;
  padding:0;border:1px solid var(--hair);border-radius:var(--radius);
  background:none;cursor:pointer;flex:0 0 auto}
.swatch::-webkit-color-swatch-wrapper{padding:2px}
.swatch::-webkit-color-swatch{border:0;border-radius:2px}

/* list-valued settings: the same chip editor everywhere */
.led{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end}
.led .pill{padding:3px 8px;font-size:9.5px}
.led-add{display:flex;gap:6px;width:100%;justify-content:flex-end;
  margin-top:4px}
.led-add .input{flex:1 1 auto;max-width:220px}

.set-row .fld{display:block}
.opt-fld{display:block;min-width:0}
.opt-fld .label{display:block;margin-bottom:5px}
.adv-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.adv-row .pill{flex:0 0 auto}

/* --- table view --------------------------------------------------------- */
.wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:620px}
th{font-family:var(--mono);font-size:9.5px;text-transform:uppercase;
  letter-spacing:.14em;color:var(--faint);font-weight:400;text-align:left;
  padding:9px 12px;border-bottom:1px solid var(--hair)}
td{padding:calc(var(--trh) / 3) 12px;border-bottom:1px solid var(--hair-2);
  font-size:12.5px;vertical-align:top}
td.t,td.n{font-family:var(--mono);font-size:11px;color:var(--faint);
  white-space:nowrap;font-variant-numeric:tabular-nums}
td.n{text-align:right;color:var(--muted)}
td.ex{color:var(--muted);overflow-wrap:anywhere}
tr.ev{cursor:pointer}
tr.ev:hover{background:var(--wash)}
tr.detail td{background:var(--bg);border-bottom:1px solid var(--hair)}
tr.detail pre{margin:0;font-family:var(--mono);font-size:11.5px;
  line-height:1.65;white-space:pre-wrap;word-break:break-word;color:var(--muted)}
.srcwrap{display:inline-flex;align-items:center;gap:7px}
.srcwrap i{width:var(--dot);height:var(--dot);border-radius:999px;flex:0 0 auto}
.muted{color:var(--faint)}

.foot{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;
  font-family:var(--mono);font-size:10px;color:var(--faint);margin-top:12px}

/* --- responsive --------------------------------------------------------- */
@media (max-width:1000px){
  .shell{grid-template-columns:minmax(0,1fr);grid-template-areas:"side" "main";
    gap:18px;padding:18px 18px 60px}
  .side{max-height:170px;overflow:auto;padding-right:2px}
  .sess{max-height:110px}
  .opts{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
}
@media (max-width:640px){
  body{font-size:14px}
  .shell{padding:14px 12px 52px}
  .nav-inner{padding:9px 12px;gap:7px 10px}
  .logo{font-size:17px}
  .tiles{grid-template-columns:repeat(auto-fill,minmax(132px,1fr));gap:8px}
  .tile{padding:10px}
  .tile .n{font-size:21px}
  .panel-b{padding:12px}
  .step{padding-left:24px}
  .step > .node{left:11px}
  .prompt{font-size:13.5px}
  .legend .nm{max-width:12ch}
  .turn-h{padding:9px 11px}
  /* the status strip wraps instead of scrolling sideways */
  .status .seg{border-right:0;padding-right:0}
  .status .cbar{width:64px}
  /* the waterfall keeps its configured gutter: the lane labels are the
     setting's whole point, so a breakpoint does not get to overrule it */
  .wf-row,.wf-axis{gap:6px}
  .wf-l{font-size:8.5px}
  .wfseg{min-width:2px}
  .wf-h{gap:4px 9px}
  .wf-h .badge{font-size:9px;padding:2px 6px}
  .wf-legend{gap:6px 12px}
  .wf-legend em{display:none}
  /* 100vw includes the scrollbar, which pushes the panel 14px off the left
     edge. Pin both edges instead -- the fixed box then matches the actual
     viewport however wide the scrollbar is. */
  .opts{grid-template-columns:minmax(0,1fr)}
  .panel-h{align-items:flex-start}
}

/* Reduced motion: unlayered so it wins. The page animates nothing on
   purpose, so there is no "from opacity 0" state to settle -- only the
   new-event flash, which is pinned to a static tint instead of blinking. */
@media (prefers-reduced-motion: reduce){
  *,*::before,*::after{
    animation-duration:.001ms !important;
    animation-iteration-count:1 !important;
    transition-duration:.001ms !important;
  }
  .step.flash{animation:none !important;
    background:color-mix(in oklab, var(--brand) 11%, transparent)}
}
"""


JS = r"""
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s==null?'':s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
/* Text nodes only: quotes are safe in element content and escaping them
   would break the JSON tokenizer below. */
const escTxt = s => String(s==null?'':s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

function human(n){
  n = Number(n)||0;
  if(n < 1000) return String(n);
  if(n < 1e6) return (n/1000).toFixed(1)+'k';
  if(n < 1e9) return (n/1e6).toFixed(2)+'M';
  return (n/1e9).toFixed(2)+'b';
}

/* One hue per source, so a colour means the same thing everywhere on the page
   -- share bar, legend, tiles, nodes. The hues are custom properties rather
   than values baked in here, because each one is a setting: changing a source
   colour in Settings has to move every place that source is drawn, and the
   way to guarantee that is for every place to read the same variable. */
function srcVar(s){
  if(s.indexOf('inject:') === 0) return '--src-inject';
  if(s.indexOf('system:') === 0) return '--src-system';
  if(s === 'reasoning') return '--src-reasoning';
  if(s === 'tool call') return '--src-toolcall';
  if(s === 'tool result') return '--src-toolresult';
  if(s === 'user prompt') return '--src-prompt';
  if(s === 'text') return '--src-text';
  return '--src-other';
}
const hueColor = s => 'var('+srcVar(s)+')';

function jsonHTML(raw){
  let obj;
  try{ obj = JSON.parse(raw); }
  catch(e){ return '<pre class="json">'+escTxt(raw||'')+'</pre>'; }
  const pretty = JSON.stringify(obj, null, 2);
  const out = escTxt(pretty).replace(
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
    (m, str, colon, kw) => {
      if(str !== undefined)
        return '<span class="'+(colon?'jk':'js')+'">'+str+'</span>'+(colon||'');
      if(kw) return '<span class="kb">'+m+'</span>';
      return '<span class="jn">'+m+'</span>';
    });
  return '<pre class="json">'+out+'</pre>';
}

let STATE = {session:null,summary:[],billed:{},sessions:[],series:[],status:null,live:false};
/* Events accumulate across polls. Row indices point into THIS array, so it
   must never be replaced by a partial server slice. */
let EVENTS = [];
let SHOWN = 0;

let VIEW = 'timeline';
let RESULT_OF = {};   /* call index -> index of the result that answers it */
let CALL_OF = {};     /* the inverse, so a result can name its own tool */
let LAST_TURN_AT = 0; /* index where the newest turn begins */
let NTURNS = 0;
/* Source filters are a SET of source prefixes, not one choice: "inputs and
   tool calls" is a question worth being able to ask in one view. Empty means
   no source filtering at all. */
let FILTER = [];
/* Tracking options. Everything a view hides is decided in matches(), so the
   flow, the table and the counts can never disagree about what is filtered. */
let OPT = {q:'', qRaw:'', regex:false, tool:'', minTok:0, noinject:false,
           err:false, lastTurn:false, hidden:[]};

function money(c){
  const d = Math.max(0, Math.min(6, Number(CFG.cost_decimals)));
  const n = (isFinite(d) ? d : 2);
  const sym = CFG.currency == null ? '$' : String(CFG.currency).slice(0, 4);
  return sym + (c < 0.01 && n < 4 ? c.toFixed(4) : c.toFixed(n));
}

/* The context bar's colour is a reading of how full the window is, so the two
   thresholds are settings rather than taste -- what counts as "nearly full"
   depends on the model's window, and only the person watching knows that. */
function pctColor(p){
  if(CFG.bar_colors === false) return 'var(--fg)';
  const warn = Number(CFG.ctx_warn_pct), danger = Number(CFG.ctx_danger_pct);
  const w = isFinite(warn) ? warn : 70;
  const g = (isFinite(danger) ? danger : 90);
  if(p >= g) return '#B3261E';
  if(p >= w) return '#8A6A16';
  return 'var(--brand)';
}

function secOf(t){
  const m = /^(\d\d):(\d\d):(\d\d)$/.exec(t||'');
  return m ? (+m[1])*3600 + (+m[2])*60 + (+m[3]) : null;
}

/* --------------------------------------------------------------- renderers */
function renderStatus(){
  const s = STATE.status;
  if(!s){
    $('#status').innerHTML = '<span class="seg miss">no status line data</span>';
    return;
  }
  /* The window and the bar width are settings, not facts from the transcript:
     the terminal has its own CLAUDE_CONTEXT_LIMIT, and this is the dashboard's. */
  const limit = Math.max(1000, Number(CFG.context_limit) || 200000);
  const p = Math.max(0, Math.min(100, (s.ctx||0) / limit * 100));
  const c = pctColor(p);
  const cells = Math.max(4, Math.min(40, Number(CFG.bar_cells) || 12));
  /* Two cost figures exist and they disagree (Claude Code computes its own;
     the gateway publishes ratios that imply ~2.4x more). Which one is shown is
     a setting; when both are shown the second is labelled, never blended in.
     The derived figure is re-priced here so the quota knob moves it live. */
  const derived = (typeof s.cost_quota === 'number' && s.cost_quota != null && CFG.quota_per_usd)
    ? s.cost_quota / Number(CFG.quota_per_usd)
    : s.cost_derived;
  const reported = s.cost_source === 'claude-code' ? s.cost : null;
  let cost = '';
  if(reported != null || derived != null){
    const pick = CFG.cost_source === 'derived' ? 'derived'
               : CFG.cost_source === 'reported' ? 'reported' : 'both';
    let shown, tag, other = null;
    if(pick === 'derived'){ shown = derived; tag = 'gateway ratios'; }
    else if(reported != null){ shown = reported; tag = 'claude code'; other = derived; }
    else { shown = derived; tag = 'gateway ratios (no figure from Claude Code)'; }
    if(shown == null){ shown = 0; }
    const gap = (pick === 'both' && other != null && Math.abs(other - shown) > 0.01)
      ? '<span class="proj"> · est '+money(other)+'</span>' : '';
    cost = '<span class="seg cost" title="source: '+esc(tag)+'">'+
      money(shown)+gap+'</span>';
  }
  /* Every segment is a setting. A status strip you cannot trim does not fit a
     narrow window, and which numbers matter depends on what you are doing. */
  const segs = [];
  if(CFG.st_model !== false)
    segs.push('<span class="seg"><span class="model">'+esc(s.model||'model')+'</span>'+
      (s.project ? '<span class="proj">'+esc(s.project)+'</span>' : '')+'</span>');
  if(CFG.st_ctx !== false)
    segs.push('<span class="seg"><span class="cbar" style="width:'+(cells*5.5).toFixed(1)+'px">'+
      '<i style="width:'+p.toFixed(1)+'%;background:'+c+'"></i></span>'+
      '<span class="pct" style="color:'+c+'">'+p.toFixed(0)+'%</span>'+
      '<span class="proj">ctx '+human(s.ctx)+'/'+human(limit)+'</span></span>');
  if(CFG.st_in !== false) segs.push('<span class="seg up">↑ in '+human(s.in)+'</span>');
  if(CFG.st_out !== false) segs.push('<span class="seg down">↓ out '+human(s.out)+'</span>');
  if(CFG.show_lifetime !== false && s.lifetime)
    segs.push('<span class="seg sum">Σ '+human(s.lifetime)+'</span>');
  if(CFG.st_msgs !== false) segs.push('<span class="seg proj">'+s.msgs+' msg</span>');
  if(CFG.st_cost !== false && cost) segs.push(cost);
  $('#status').innerHTML = segs.join('') || '<span class="seg miss">every segment is off</span>';
}

function renderHead(){
  const s = STATE.session||'';
  document.title = 'Trajectory — '+s;
  $('#crumb').textContent = '/trajectory/'+s;
  $('#h1').textContent = 'Session '+s;
  $('#smeta').innerHTML =
    '<span><b>'+(STATE.records||0).toLocaleString()+'</b> log records</span>'+
    '<span><b>'+(STATE.total||0).toLocaleString()+'</b> model-visible events</span>'+
    '<span><b>'+EVENTS.length.toLocaleString()+'</b> in view</span>';
}

/* Folder slugs are long and there are usually more sessions than folders, so
   the list is built from the sessions actually on disk, with counts. */
function renderFolders(){
  const sel = $('#folder'), keep = sel.value;
  const n = {};
  (STATE.sessions||[]).forEach(s=>{ n[s.folder] = (n[s.folder]||0)+1; });
  const names = Object.keys(n).sort((a,b)=>
    (a.indexOf('-')===0?1:0)-(b.indexOf('-')===0?1:0) || a.localeCompare(b));
  sel.innerHTML = '<option value="">All folders · '+((STATE.sessions||[]).length)+
    ' sessions</option>' + names.map(f =>
    '<option value="'+esc(f)+'">'+esc(f)+' · '+n[f]+'</option>').join('');
  if(names.indexOf(keep) >= 0) sel.value = keep;
}

function renderSessions(){
  const q = ($('#search').value||'').toLowerCase();
  const folder = $('#folder').value;
  let list = (STATE.sessions||[]).filter(s =>
    (!folder || s.folder === folder) &&
    (!q || s.id.toLowerCase().includes(q) ||
     (s.project||'').toLowerCase().includes(q) ||
     (s.folder||'').toLowerCase().includes(q)));
  const sort = CFG.sess_sort || 'recent';
  list = list.slice().sort((a,b) =>
    sort === 'name' ? String(a.id).localeCompare(String(b.id))
    : sort === 'size' ? (b.size_bytes||0) - (a.size_bytes||0)
    : 0);   /* 'recent' is the order the server sent, newest first */
  const cap = Math.max(5, Number(CFG.sess_limit) || 40);
  const total = list.length;
  if(list.length > cap) list = list.slice(0, cap);
  const meta = CFG.sess_meta !== false;
  const size = CFG.sess_tokens !== false;
  $('#sess').innerHTML = list.map(s =>
    '<li><button data-id="'+esc(s.id)+'" aria-current="'+(s.id===STATE.session)+'">'+
      '<span class="sid"><i class="dot" style="'+(s.current?'':'opacity:.22')+'"></i>'+
        esc(s.id)+'</span>'+
      (meta ? '<span class="proj">'+esc(s.project)+'</span>' : '')+
      ((meta || size)
        ? '<span class="meta">'+
            (meta ? '<span>'+esc(s.mtime)+'</span>' : '')+
            (size ? '<span>'+esc(s.size)+'</span>' : '')+
          '</span>'
        : '')+
    '</button></li>').join('')
    || '<li><p class="empty">No sessions match.</p></li>';
  $('#records').textContent = (STATE.records||0).toLocaleString()+' records';
  $('#scount').textContent = list.length+' of '+total+' shown';
}

/* The summary the server sends is ordered by tokens. Which order reads best
   depends on the question -- biggest first for "where did it go", alphabetical
   for finding one source -- so the order is a setting. */
function summaryRows(){
  let rows = (STATE.summary||[]).slice();
  const hidden = (CFG.hide_sources||[]);
  if(hidden.length)
    rows = rows.filter(x => !hidden.some(h => String(x.source).indexOf(h) === 0));
  const order = CFG.source_order || 'tokens';
  if(order === 'name') rows.sort((a,b)=>String(a.source).localeCompare(String(b.source)));
  else if(order === 'events') rows.sort((a,b)=>b.events-a.events);
  else rows.sort((a,b)=>b.tokens-a.tokens);

  /* A source holding a rounding error's worth of tokens is a sliver in the
     share bar and its own tile. Below the threshold they are folded into one
     band, which is the difference between a readable bar and a comb. */
  const min = Number(CFG.share_min_pct);
  if(isFinite(min) && min > 0){
    const total = rows.reduce((a,b)=>a+b.tokens, 0) || 1;
    const keep = [], fold = [];
    rows.forEach(x => ((x.tokens/total*100) < min ? fold : keep).push(x));
    if(fold.length > 1){
      keep.push({source:'other sources', events: fold.reduce((a,b)=>a+b.events,0),
        tokens: fold.reduce((a,b)=>a+b.tokens,0),
        pct: fold.reduce((a,b)=>a+b.pct,0), folded: fold.length});
    } else keep.push(...fold);
    rows = keep;
  }
  return rows;
}

function renderStats(){
  const s = summaryRows();
  const total = s.reduce((a,b)=>a+b.tokens,0)||1;

  const share = $('#share'), legend = $('#legend'), tiles = $('#tiles');
  if(share){
    share.hidden = CFG.show_share === false;
    if(!share.hidden) share.innerHTML = s.map(x =>
      '<i style="width:'+(x.tokens/total*100).toFixed(3)+'%;background:'+
        hueColor(x.source)+'" title="'+esc(x.source)+' · '+x.pct.toFixed(1)+'%"></i>'
    ).join('');
  }
  if(legend){
    legend.hidden = CFG.show_legend === false;
    if(!legend.hidden) legend.innerHTML = s.map(x =>
      '<span><i class="dot" style="background:'+hueColor(x.source)+'"></i>'+
        '<span class="nm">'+esc(x.source)+'</span><em>'+x.pct.toFixed(1)+'%</em>'+
        (x.folded ? '<em>· '+x.folded+'</em>' : '')+'</span>'
    ).join('');
  }
  if(tiles){
    tiles.hidden = CFG.show_tiles === false;
    const cols = Math.max(1, Math.min(8, Number(CFG.tile_cols) || 5));
    tiles.style.gridTemplateColumns = 'repeat('+cols+', minmax(0,1fr))';
    if(!tiles.hidden){
      const max = Math.max(...s.map(x=>x.tokens), 1);
      tiles.innerHTML = s.map(x =>
        '<div class="tile">'+
          '<p class="src"><i class="dot" style="background:'+hueColor(x.source)+'"></i>'+
            '<span class="nm">'+esc(x.source)+'</span></p>'+
          '<p class="n">'+human(x.tokens)+'</p>'+
          '<p class="sub">'+x.events.toLocaleString()+' events · '+x.pct.toFixed(1)+'%</p>'+
          '<div class="bar"><i style="width:'+(x.tokens/max*100).toFixed(1)+'%;background:'+
            hueColor(x.source)+'"></i></div>'+
        '</div>').join('');
    }
  }

  const b = STATE.billed||{};
  $('#billed').innerHTML = [['input',b.in],['cache read',b.cr],
    ['cache write',b.cw],['output',b.out]]
    .map(([k,v]) => '<div><span class="k">'+k+'</span>'+human(v)+'</div>').join('');
}

/* Tokens per minute, as the transcript logs them. The chart's height is a
   custom property; how many columns it is drawn with is not, because
   resampling has to happen here rather than in CSS. */
function renderSpark(){
  let s = (STATE.series||[]).slice();
  const bucket = Math.max(8, Math.min(240, Number(CFG.spark_buckets) || 48));
  if(s.length > bucket){
    const per = s.length / bucket, out = [];
    for(let i = 0; i < bucket; i++){
      const lo = Math.floor(i*per), hi = Math.max(lo+1, Math.floor((i+1)*per));
      const slice = s.slice(lo, hi);
      if(!slice.length) continue;
      out.push({t: slice[0].t, tokens: slice.reduce((a,b)=>a+b.tokens,0),
                events: slice.reduce((a,b)=>a+b.events,0)});
    }
    s = out;
  }
  if(!s.length){ $('#spark').innerHTML = ''; $('#spark-meta').textContent = 'no data'; return; }
  const max = Math.max(...s.map(d=>d.tokens), 1);
  const n = s.length, h = 40, w = Math.max(n*7, 140);
  const bw = w/n;
  const bars = s.map((d,i)=>{
    const bh = Math.max(1, Math.round(d.tokens/max*h));
    return '<rect x="'+(i*bw).toFixed(2)+'" y="'+(h-bh)+'" width="'+Math.max(1,bw-1).toFixed(2)+
      '" height="'+bh+'" fill="'+(i===n-1 ? 'var(--brand)' : 'var(--src-toolcall)')+
      '" opacity="'+(i===n-1?1:0.55)+'"><title>'+esc(d.t)+' · '+human(d.tokens)+
      ' tok · '+d.events+' events</title></rect>';
  }).join('');
  $('#spark').innerHTML = '<svg class="spark" viewBox="0 0 '+w+' '+h+
    '" preserveAspectRatio="none" aria-label="tokens per minute">'+bars+'</svg>';
  $('#spark-meta').textContent = s.length+' min · peak '+human(max)+' tok/min · '+
    esc(s[0].t)+'–'+esc(s[s.length-1].t);
}

/* Jumping from a trace to the row it stands for. Filters can hide the
   target, so they are cleared first -- "show me this event" beats
   "respect the filter and show me nothing". */
function jumpTo(i){
  if(activeOpts())
    resetFilters();
  if(VIEW !== 'table') setView('table');
  const tr = $('#rows tr[data-i="'+i+'"]');
  if(!tr) return;
  tr.scrollIntoView({block:'center'});
  tr.classList.add('flash');
  setTimeout(()=>tr.classList.remove('flash'), 1400);
  if(!tr.classList.contains('open')) tr.click();
}

/* ------------------------------------------------- the tooltip and inspect */
/* Native `title` takes a second to appear, cannot be styled, and never shows
   on the touch devices this page gets opened on. The tooltip is one element
   that follows the pointer, fed from the data the trace already carries. */
function tipShow(html, x, y){
  const t = $('#tip');
  if(!t || !html){ tipHide(); return; }
  t.innerHTML = html;
  t.hidden = false;
  const r = t.getBoundingClientRect();
  let left = x + 14, top = y + 18;
  if(left + r.width > innerWidth - 8) left = Math.max(8, x - r.width - 14);
  if(top + r.height > innerHeight - 8) top = Math.max(8, y - r.height - 14);
  t.style.left = left+'px';
  t.style.top = top+'px';
}
function tipHide(){
  const t = $('#tip');
  if(t) t.hidden = true;
}
function tipRow(k, v){
  return '<span class="r"><span class="k">'+esc(k)+'</span> '+esc(v)+'</span>';
}
function tipForEvent(i){
  const e = EVENTS[i];
  if(!e) return '';
  const n = Math.max(0, Math.min(400, Number(CFG.tip_excerpt)));
  const cut = (isFinite(n) ? n : 110);
  return '<span class="hd">'+esc(e.source === 'tool call' ? (e.name||'tool') : e.source)+'</span>'+
    tipRow('at', e.t) + tipRow('tokens', human(e.tokens||0)) +
    (e.error ? '<span class="r">error</span>' : '') +
    (e.excerpt && cut ? '<span class="r">'+esc(String(e.excerpt).slice(0, cut))+'</span>' : '');
}
function tipForSpan(el){
  const [ia, ib] = (el.dataset.inspect||'').split(',').map(Number);
  const a = EVENTS[ia], b = EVENTS[ib];
  if(!a || !b) return '';
  const ms = Math.max(0, (b.ts||0) - (a.ts||0));
  return '<span class="hd">'+esc(el.dataset.what||'span')+' · '+esc(fmtMs(ms))+'</span>'+
    tipRow('from', a.t + '  ' + (a.source==='tool call' ? (a.name||'tool call') : a.source))+
    tipRow('to', b.t + '  ' + (b.source==='tool call' ? (b.name||'tool call') : b.source))+
    tipRow('out', human(b.tokens||0) + ' tok')+
    '<span class="r k">click for the full record</span>';
}

/* --- inspect sidebar ----------------------------------------------------- */
let inspectIdx = null;
function openInspect(open){
  const d = $('#inspect');
  if(!d) return;
  d.hidden = !open;
  if(!open) inspectIdx = null;
}
function inspectHTML(ia, ib){
  const a = EVENTS[ia], b = EVENTS[ib];
  if(!a) return '<p class="empty">That record is no longer in the stream.</p>';
  const ms = Math.max(0, (b ? (b.ts||0) : (a.ts||0)) - (a.ts||0));
  const src = a.source === 'tool call' ? (a.name || 'tool call') : a.source;

  let h = '<div class="iscet"><span class="ibadge">'+
    '<i class="dot" style="background:'+hueColor(a.source)+'"></i>'+esc(src)+'</span></div>';

  h += '<div class="iscet">'+
    field('source', esc(a.source)) +
    field('at', esc(a.t) + '  <span class="k">' + esc(String(a.ts||'')) + '</span>') +
    field('tokens', human(a.tokens||0)) +
    (a.name ? field('tool', esc(a.name)) : '') +
    (a.call ? field('call id', esc(a.call), true) : '') +
    (a.for ? field('result of', esc(a.for), true) : '') +
    (a.error ? field('status', '<span style="color:#B3261E">error</span>') : '') +
  '</div>';

  if(ib != null && b){
    const bs = b.source === 'tool call' ? (b.name || 'tool call') : b.source;
    h += '<div class="iscet"><p class="label">Span ends at</p>'+
      '<div class="ibox">'+field('record', esc(bs))+
      field('at', esc(b.t)) + field('duration', fmtMs(ms)) +
      field('tokens', human(b.tokens||0))+'</div></div>';
  }

  /* The call and its result are two records that only mean anything together,
     so whichever one was clicked, both are shown -- unless the pairing was
     turned off, in which case showing it would be the surprise. */
  const pairIdx = (CFG.inspect_pair === false || ib != null)
    ? null
    : (RESULT_OF[ia] != null ? RESULT_OF[ia] : CALL_OF[ia]);
  if(pairIdx != null && EVENTS[pairIdx]){
    const p = EVENTS[pairIdx];
    const ps = p.source === 'tool call' ? (p.name||'tool call') : p.source;
    h += '<div class="iscet"><p class="label">'+
      (RESULT_OF[ia] != null ? 'Result' : 'Call')+'</p>'+
      '<div class="ibox">'+field('record', esc(ps))+
      field('at', esc(p.t)) + field('tokens', human(p.tokens||0))+'</div>'+
      '<div class="ibox" style="margin-top:8px;border:0;padding:0">'+
      (p.source === 'tool call' ? jsonHTML(p.text||p.excerpt||'') :
        '<pre class="json">'+escTxt(p.text || p.excerpt || '(no content)')+'</pre>')+
      '</div></div>';
  }

  h += '<div class="iscet"><p class="label">Payload</p><div class="ibox">'+
    (a.source === 'tool call' ? jsonHTML(a.text || a.excerpt || '(empty)')
      : '<pre class="json">'+escTxt(a.text || a.excerpt || '(no content)')+'</pre>')+
    ((!a.text && a.excerpt)
      ? '<p class="hint" style="margin-top:8px">excerpt only — full text omitted to bound the payload</p>' : '')+
    '</div></div>';

  if(CFG.inspect_raw !== false)
    h += '<div class="iscet"><p class="label">Record</p><div class="ibox">'+
      jsonHTML(JSON.stringify(EVENTS[ia], null, 2))+'</div></div>';
  return h;
}
function field(k, v, mono){
  return '<div class="if"><span class="ik">'+k+'</span>'+
    '<span class="iv'+(mono?' mono':'')+'">'+v+'</span></div>';
}
function showInspect(ia, ib){
  if(!Number.isFinite(ia) || !EVENTS[ia]) return;
  inspectIdx = ia;
  $('#inspect-title').textContent = 'Record ' + ia;
  $('#inspect-body').innerHTML = inspectHTML(ia, ib);
  const j = $('#inspect-jump');
  if(j) j.hidden = (CFG.inspect_jump === false);
  openInspect(true);
}

/* Hover: one element follows the pointer, fed from the record it is over. The
   delay is a setting because a tooltip that appears while the pointer is still
   travelling is noise, and how long "still travelling" lasts is a preference. */
let tipTimer = null;
function tipSoon(html, x, y){
  clearTimeout(tipTimer);
  const ms = Math.max(0, Math.min(1500, Number(CFG.tip_delay)));
  const wait = isFinite(ms) ? ms : 120;
  if(!wait){ tipShow(html, x, y); return; }
  tipTimer = setTimeout(() => tipShow(html, x, y), wait);
}
document.addEventListener('mouseover', ev => {
  if(CFG.tip_on === false){ tipHide(); return; }
  const seg = ev.target.closest('[data-inspect]');
  if(seg){
    if(CFG.wf_tooltip === false) { tipHide(); return; }
    tipSoon(tipForSpan(seg), ev.clientX, ev.clientY); return;
  }
  const st = ev.target.closest('.step');
  if(st){ tipSoon(tipForEvent(Number(st.dataset.i)), ev.clientX, ev.clientY); return; }
  clearTimeout(tipTimer); tipHide();
});
document.addEventListener('mouseout', ev => {
  if(ev.target.closest('[data-inspect]') || ev.target.closest('.step')){
    clearTimeout(tipTimer); tipHide();
  }
});
window.addEventListener('scroll', () => { clearTimeout(tipTimer); tipHide(); },
  {passive:true});


/* ------------------------------------------------------------- waterfall */
/* Segments are measured, never invented. Four kinds of record carry a time --
   prompt, reasoning, text, tool call, tool result -- and the gap between two
   consecutive ones is attributed to whoever was busy across it:

     prompt/result -> model output   the request round trip   "input"
     model output  -> model output   the model still going    "model"
     tool call     -> its own result the tool running         "tool"

   Nothing here can separate network time from generation time, so "input" is
   named for what it is: the wait before the model's next output appears. */
const WF_PHASES = ['user prompt', 'reasoning', 'text', 'tool call', 'tool result'];
/* Budgets, not constants: each is a settings knob (see CFG), assigned in
   applyCfg before anything reads them. */
let WF_TURNS = 12;
let WF_SEG_CAP = 900;
let WF_MIN = 0.12;
let WF_TICKS = 5;
let WF_LABELS = true;
let WF_HEADER = true;

function fmtMs(ms){
  if(ms < 1000) return Math.round(ms)+'ms';
  if(ms < 60000) return (ms/1000).toFixed(1)+'s';
  const m = Math.floor(ms/60000), s = Math.round((ms%60000)/1000);
  return m+'m '+(s<10?'0':'')+s+'s';
}

function phaseSegments(t){
  const seq = [t.at].concat(t.items).filter(i => {
    const e = EVENTS[i];
    return e && WF_PHASES.indexOf(e.source) >= 0 && e.ts != null;
  });
  const out = [];
  for(let k = 1; k < seq.length; k++){
    const ia = seq[k-1], ib = seq[k];
    const a = EVENTS[ia], b = EVENTS[ib];
    if(b.ts < a.ts) continue;             /* clock noise around a compaction */
    /* A span is drawn when either end of it survives the filters. The bars
       are positioned by real timestamps, so a dropped span leaves a gap in
       the lane rather than closing it up -- filtered-out time still reads as
       time that passed. "Either end" and not "both": requiring both makes a
       single-source filter draw an empty timeline (reasoning is rarely
       adjacent to reasoning), which reads as a broken page rather than a
       filtered one. */
    if(!matches(a, ia) && !matches(b, ib)) continue;
    let lane;
    if(a.source === 'tool call' && RESULT_OF[ia] === ib) lane = 'tool';
    else if(b.source === 'tool result') lane = 'tool';
    else if((a.source === 'user prompt' || a.source === 'tool result') &&
            b.source !== 'tool result') lane = 'input';
    else if(a.source === 'tool result' || a.source === 'user prompt') lane = 'input';
    else lane = 'model';
    const what = lane === 'tool' ? (a.name || 'tool')
      : lane === 'model' ? (b.source === 'reasoning' ? 'reasoning'
        : b.source === 'text' ? 'text' : b.source)
      : 'round trip';
    out.push({lane:lane, a:a.ts, b:b.ts, what:what, tok:b.tokens||0,
              ia:ia, ib:ib});
  }
  return out;
}

function turnSpan(t){
  let lo = Infinity, hi = -Infinity;
  [t.at].concat(t.items).forEach(i=>{
    const e = EVENTS[i];
    if(!e || e.ts == null) return;
    if(e.ts < lo) lo = e.ts;
    if(e.ts > hi) hi = e.ts;
  });
  return (lo === Infinity) ? null : {lo:lo, hi:hi};
}

function waterfallHTML(t, n){
  const span = turnSpan(t);
  if(!span) return '';
  const dur = Math.max(1, span.hi - span.lo);
  const segs = phaseSegments(t);
  /* A turn with nothing left to draw is dropped rather than left as a header
     over three empty lanes -- same rule as the flow, so "only tool calls"
     reads the same way in both views. */
  if(!segs.length && !matches(EVENTS[t.at], t.at)) return '';
  const cut = segs.length > WF_SEG_CAP;
  const use = cut ? segs.slice(0, WF_SEG_CAP) : segs;

  const rows = [['input','Input'],['model','Model'],['tool','Tools']].map(([k,label])=>{
    const bars = use.filter(s=>s.lane === k).map(s=>{
      const x = (s.a - span.lo)/dur*100;
      /* The floor is what keeps a 20ms call visible next to a 180s one; how
         low it goes is a setting, because it is the difference between "the
         bars are all lies" and "the bar is invisible". */
      const w = Math.max(WF_MIN, (s.b - s.a)/dur*100);
      return '<i class="wfseg '+k+'" data-inspect="'+s.ia+','+s.ib+'"'+
        ' data-what="'+esc(s.what)+'"'+
        ' style="left:'+x.toFixed(3)+'%;width:'+w.toFixed(3)+'%"></i>';
    }).join('');
    const total = use.filter(s=>s.lane === k).reduce((a,s)=>a + (s.b - s.a), 0);
    return '<div class="wf-row"'+(WF_LABELS ? '' : ' style="grid-template-columns:minmax(0,1fr)"')+'>'+
      (WF_LABELS ? '<span class="wf-l" title="'+label+' '+fmtMs(total)+
        ' over '+use.filter(s=>s.lane===k).length+' span(s)">'+label+'</span>' : '')+
      '<div class="wf-t">'+bars+'</div></div>';
  }).join('');

  const nticks = Math.max(2, Math.min(11, WF_TICKS));
  const ticks = Array.from({length: nticks}, (_,i) => i/(nticks-1)).map(f =>
    '<span style="left:'+(f*100).toFixed(2)+'%">'+
      (f === 0 ? '0' : fmtMs(dur*f))+'</span>').join('');

  const nested = t.items.filter(i=>isNested(i)).length;
  /* Three empty lanes are sixty pixels of nothing. A turn whose only content
     is a prompt, or whose spans the filters removed, says so in one line. */
  const body = use.length ? rows +
      '<div class="wf-axis"'+(WF_LABELS ? '' : ' style="grid-template-columns:minmax(0,1fr)"')+'>'+
      (WF_LABELS ? '<span></span>' : '')+
      '<div class="wf-ticks">'+ticks+'</div></div>'
    : '<p class="turn-cut hint">'+
      (segs.length ? 'all of this turn’s spans are filtered out'
                   : 'no measurable spans — nothing here took time')+'</p>';
  return '<div class="wf" data-at="'+t.at+'">'+
    (WF_HEADER ? '<div class="wf-h">'+
      '<span class="badge">Turn '+n+'</span>'+
      '<span class="turn-m">'+esc(t.t)+'</span>'+
      '<span class="turn-m">'+t.items.length+' record'+(t.items.length===1?'':'s')+
        (nested ? ' · '+nested+' nested' : '')+'</span>'+
      '<span class="turn-m">'+human(t.tokens)+' tok</span>'+
      '<span class="turn-m dur">'+fmtMs(dur)+'</span>'+
    '</div>' : '')+
    body+
    (cut ? '<p class="turn-cut hint">'+segs.length+' spans in this turn — '+
      'showing the first '+WF_SEG_CAP+'</p>' : '')+
  '</div>';
}

/* Newest turn first: a waterfall is read to see where the time went, and the
   turn you are waiting on is the one at the bottom of the log. */
function renderWaterfall(append, from){
  const box = $('#wf');
  const turns = buildTurns(EVENTS);
  if(!turns.length){
    box.innerHTML = '<div class="empty">No events in this session.</div>';
    return;
  }
  const ordered = turns.slice().reverse();
  const shown = SHOW_ALL ? ordered : ordered.slice(0, WF_TURNS);
  const hiddenCount = ordered.length - shown.length;
  box.innerHTML =
    (hiddenCount ? '<div class="flow-more"><button class="pill" data-show-all>'+
      hiddenCount+' earlier turn'+(hiddenCount===1?'':'s')+' hidden — show all</button></div>' : '')+
    shown.map((t,k)=>waterfallHTML(t, ordered.length - k)).join('');
}

/* ---------------------------------------------------------------- the flow */
function buildTurns(ev){
  const turns = []; let cur = null;
  ev.forEach((e,i)=>{
    if(!cur || e.source==='user prompt'){
      /* `at` is the event INDEX (so filters and "last turn" can ask where a
         turn begins) and `t` is its clock time for display. They are
         different things and conflating them silently broke both. */
      cur = {at:i, t:e.t, prompt:(e.source==='user prompt'? e : null),
             items:[], tokens:0};
      turns.push(cur);
      if(e.source==='user prompt') return;   /* the prompt is the header */
    }
    cur.items.push(i);
    cur.tokens += e.tokens||0;
  });
  return turns;
}

/* Pair each call with the result that carries its tool_use id. The ids match
   exactly in the transcript, so this is a lookup rather than a guess. */
function pairResults(ev){
  const calls = {};
  ev.forEach((e,i)=>{ if(e.source==='tool call' && e.call) calls[e.call] = i; });
  const out = {};
  ev.forEach((e,i)=>{
    if(e.source==='tool result' && e.for && calls[e.for] != null) out[calls[e.for]] = i;
  });
  return out;
}

/* How much of a record the collapsed row shows. The text is already truncated
   server-side to bound the payload; this is the tighter, readable cut, and it
   is a setting because "one line" means different things on different screens. */
function clipExcerpt(t){
  const n = Math.max(20, Math.min(600, Number(CFG.stream_excerpt)));
  const cut = isFinite(n) ? n : 160;
  const s = String(t == null ? '' : t);
  return s.length > cut ? s.slice(0, cut) + '…' : s;
}

function shortBody(e){
  if(e.source==='tool call'){
    /* Colour the JSON straight away rather than only on expand -- the shape
       of a tool call is the most useful thing on the page. Older events ship
       an excerpt only, and fall back to the one-line form. */
    if(e.text && CFG.flow_json !== false) return '<div class="clamp">'+jsonHTML(e.text)+'</div>';
    return '<pre class="cmd clamp">'+escTxt(clipExcerpt(e.text || e.excerpt))+'</pre>';
  }
  const t = e.excerpt || '';
  if(!t) return '<p class="txt muted">(no content)</p>';
  return '<p class="txt clamp">'+escTxt(clipExcerpt(t))+'</p>';
}

function fullBody(e){
  if(e.source==='tool call')
    return jsonHTML(e.text || e.excerpt || '');
  const t = e.text || e.excerpt || '';
  const note = (!e.text && e.excerpt)
    ? '<p class="hint">excerpt only — full text omitted to bound the payload</p>' : '';
  return note + '<p class="txt full">'+escTxt(t)+'</p>';
}

function stepHTML(i, nested){
  const e = EVENTS[i];
  if(!e) return '';
  const call = e.source==='tool call';
  const badge = call ? esc(e.name||'tool') : esc(e.source);
  return '<li class="step'+(nested?' sub':'')+'" data-i="'+i+'" data-src="'+esc(e.source)+'">'+
      (nested ? '' : '<span class="node" style="background:'+hueColor(e.source)+'"></span>')+
      '<div class="step-h">'+
        '<span class="badge'+(call?' tool':'')+'">'+badge+'</span>'+
        '<span class="step-m">'+human(e.tokens)+' tok · '+esc(e.t)+'</span>'+
      '</div>'+
      '<div class="step-b">'+shortBody(e)+'</div>'+
      (nested ? '' : (RESULT_OF[i] != null ? stepHTML(RESULT_OF[i], true) : ''))+
      (CFG.debug_json ? '<pre class="json" style="margin-top:6px">'+
        escTxt(JSON.stringify(e))+'</pre>' : '')+
    '</li>';
}

function turnHTML(t, n, cap){
  const all = t.items.filter(i => !isNested(i));
  const cut = (cap && all.length > cap) ? all.length - cap : 0;
  const steps = cut ? all.slice(cut) : all;
  return '<section class="turn" data-at="'+t.at+'">'+
    '<header class="turn-h">'+
      '<span class="badge">Turn '+n+'</span>'+
      '<span class="turn-m">'+esc(t.t)+'</span>'+
      '<span class="turn-m">'+all.length+' step'+(all.length===1?'':'s')+
        ' · '+human(t.tokens)+' tok</span>'+
    '</header>'+
    (t.prompt ? '<p class="prompt">'+escTxt(t.prompt.excerpt)+'</p>' : '')+
    (cut ? '<p class="turn-cut hint">'+cut+' earlier step'+(cut===1?'':'s')+
      ' in this turn hidden — show all</p>' : '')+
    '<ol class="steps">'+steps.map(i=>stepHTML(i,false)).join('')+'</ol>'+
  '</section>';
}

/* A result renders inside its call. Turning that off makes both records plain
   siblings, which is what you want when you are counting records rather than
   reading one. The inverse map is only trusted when nesting is on, so a
   filtered or un-nested view can never half-nest. */
function isNested(i){
  if(CFG.flow_nested === false) return false;
  for(const k in RESULT_OF) if(RESULT_OF[k] === i) return true;
  return false;
}

/* A long session renders a six-figure-pixel column if shown whole. Turns in a
   long agent session can each hold a hundred steps, so the budget is spent on
   *steps* rather than turns -- turn count bounds nothing. The flow opens on
   the most recent steps; live appends continue from there. */
let STEP_BUDGET = 160;
let STEP_CAP = 60;
let STEP_CAP_OLD = 60;
let SHOW_ALL = false;
/* True when the flow is rendering the whole session. Filtering has to see
   every event to be able to find one, so an active filter forces this on --
   otherwise a match outside the rendered tail would silently show nothing. */
let FULL = false;

/* Expanding a step swaps its body for the full one. Both the click and the
   "open the newest step" setting go through here, so the two cannot disagree
   about what an open step is. */
function openStep(step){
  const i = Number(step.dataset.i);
  const b = step.querySelector(':scope > .step-b');
  const open = !step.classList.contains('open');
  step.classList.toggle('open', open);
  if(b) b.innerHTML = open ? fullBody(EVENTS[i]||{}) : shortBody(EVENTS[i]||{});
}

/* Index of the earliest turn to render, walking back until the budget is
   spent. Numbering stays absolute because the full turn list is known. */
function firstVisibleTurn(turns){
  let steps = 0, start = turns.length;
  for(let i = turns.length - 1; i >= 0; i--){
    steps += turns[i].items.length;
    start = i;
    if(steps >= STEP_BUDGET) break;
  }
  return start;
}

function renderFlow(append, from){
  const flow = $('#flow');
  const turns = buildTurns(EVENTS);
  if(!turns.length){
    flow.innerHTML = '<div class="empty">No events in this session.</div>';
    NTURNS = 0;
    return;
  }
  LAST_TURN_AT = turns[turns.length-1].at;
  const hidden = (!SHOW_ALL && !FULL && !append) ? firstVisibleTurn(turns) : 0;
  /* The turn you are working in is worth more of the page than the thirty
     behind it, so it gets its own cap. */
  const newest = turns.length - 1;
  const capFor = (i) => (SHOW_ALL || FULL) ? 0
    : (i === newest ? STEP_CAP : STEP_CAP_OLD);
  if(!append){
    flow.innerHTML =
      (hidden ? '<div class="flow-more"><button class="pill" data-show-all>'+
        hidden+' earlier turn'+(hidden===1?'':'s')+' hidden — show all</button></div>' : '')+
      turns.slice(hidden).map((t,i)=>turnHTML(t, hidden+i+1, capFor(hidden+i))).join('');
    NTURNS = turns.length;
  } else if(turns.length === NTURNS && flow.lastElementChild){
    /* the in-flight turn grew -- re-render just that one */
    flow.lastElementChild.outerHTML =
      turnHTML(turns[turns.length-1], turns.length, capFor(turns.length-1));
  } else {
    flow.insertAdjacentHTML('beforeend',
      turns.slice(NTURNS).map((t,i)=>turnHTML(t, NTURNS+i+1, capFor(NTURNS+i))).join(''));
    NTURNS = turns.length;
  }
  if(append && flashOn()){
    $$('#flow .step').forEach(el=>{
      if(Number(el.dataset.i) >= from) el.classList.add('flash');
    });
  }
  if(!append && CFG.flow_expand_last === true) $$('#flow .turn').forEach(turn => {
    const last = turn.querySelector(':scope > .steps > .step:last-child');
    if(last) openStep(last);
  });
  if(activeOpts()) applyFilter();
}

/* Which columns the table draws, in order. Every column is a setting, so the
   table can be trimmed to the two things a given question needs -- and the
   detail row that opens under a record has to span whatever is left. */
function tableCols(){
  const cols = [];
  if(CFG.col_time !== false) cols.push({k:'t', label:'Time', cls:'t'});
  if(CFG.col_source !== false) cols.push({k:'src', label:'Source'});
  if(CFG.col_name !== false) cols.push({k:'name', label:'Name'});
  if(CFG.col_tokens !== false) cols.push({k:'tok', label:'Tokens', cls:'n', right:true});
  if(CFG.col_text !== false) cols.push({k:'ex', label:'Detail', cls:'ex'});
  if(!cols.length) cols.push({k:'t', label:'Time', cls:'t'});
  return cols;
}
let TCOLS = [];

function tableCell(c, e){
  if(c.k === 't') return '<td class="t">'+esc(e.t)+'</td>';
  if(c.k === 'src') return '<td><span class="srcwrap">'+
    '<i style="background:'+hueColor(e.source)+'"></i><span>'+esc(e.source)+'</span></span></td>';
  if(c.k === 'name') return '<td class="t">'+esc(e.name || '—')+'</td>';
  if(c.k === 'tok') return '<td class="n">'+human(e.tokens)+'</td>';
  /* Full text is off by default: the whole point of the table is one line per
     record, and the full payload is one click away in the detail row. */
  const body = (CFG.table_full === true) ? (e.text || e.excerpt) : e.excerpt;
  return '<td class="ex">'+(esc(body)||'<span class="muted">—</span>')+'</td>';
}

function renderTable(append, from){
  const tbody = $('#rows');
  const cap = Math.max(20, Number(CFG.table_rows) || 400);
  if(!append){
    TCOLS = tableCols();
    $('#tablewrap').querySelector('thead').innerHTML =
      '<tr>'+TCOLS.map(c => '<th'+(c.right ? ' style="text-align:right"' : '')+'>'+
        esc(c.label)+'</th>').join('')+'</tr>';
    /* One row per record, and a long session has six figures of them. The cap
       is spent on the newest, which is the end you are reading. */
    const start = Math.max(0, EVENTS.length - cap);
    if(start) tbody.innerHTML = '';
    const note = $('#tablenote');
    if(note) note.textContent = start
      ? 'showing the newest '+cap.toLocaleString()+' of '+
        EVENTS.length.toLocaleString()+' records' : '';
  }
  const base = append ? SHOWN : Math.max(0, EVENTS.length - cap);
  const fresh = append ? EVENTS.slice(SHOWN) : EVENTS.slice(base);
  if(!fresh.length){
    if(!append) tbody.innerHTML =
      '<tr><td colspan="'+TCOLS.length+'"><div class="empty">No events.</div></td></tr>';
    SHOWN = EVENTS.length; return;
  }
  tbody.insertAdjacentHTML('beforeend', fresh.map((e,k)=>{
    const row = '<tr class="ev" data-i="'+(base+k)+'" data-src="'+esc(e.source)+'">'+
      TCOLS.map(c=>tableCell(c,e)).join('')+'</tr>';
    /* The raw record, for when the columns are not the whole story. Off by
       default: it doubles the row count and makes the table unreadable. */
    return row + (CFG.debug_json
      ? '<tr class="detail"><td colspan="'+TCOLS.length+'">'+
        jsonHTML(JSON.stringify(e, null, 2))+'</td></tr>' : '');
  }).join(''));
  SHOWN = EVENTS.length;
  if(append && flashOn()) $$('#rows tr.ev').slice(-fresh.length).forEach(tr=>tr.classList.add('flash'));
  if(activeOpts()) applyFilter();
}

/* --------------------------------------------------------------- filtering */
/* One predicate decides visibility for every view. A step hidden in the flow
   is hidden in the table and missing from the count, because there is only
   one place that answers "does this event count?". */
function activeOpts(){
  return !!(FILTER.length || OPT.q || OPT.tool || OPT.minTok || OPT.noinject ||
            OPT.err || OPT.lastTurn || (OPT.hidden||[]).length);
}

function matches(e, i){
  if(!e) return false;
  const src = e.source || '';
  /* Sources the settings page removes entirely. Kept out of the share bar, the
     tiles and the stream through this one predicate, so "hidden" cannot mean
     three different things in three views. */
  const hid = OPT.hidden || [];
  if(hid.length && hid.some(h => src.indexOf(h) === 0)) return false;
  if(FILTER.length && !FILTER.some(f => src.indexOf(f) === 0)) return false;
  if(OPT.noinject && src.indexOf('inject:') === 0) return false;
  if(OPT.minTok && (e.tokens||0) < OPT.minTok) return false;
  if(OPT.lastTurn && i < LAST_TURN_AT) return false;
  if(OPT.tool){
    // A result belongs to its call, so filtering by tool keeps the answer too.
    let name = e.name;
    if(!name && e.for && CALL_OF[i] != null) name = (EVENTS[CALL_OF[i]]||{}).name;
    if(!name || name.toLowerCase().indexOf(OPT.tool) < 0) return false;
  }
  if(OPT.err){
    // The harness marks failures itself; the regex is a fallback for results
    // that report an error only in their text.
    const isErr = e.error || (src === 'tool result' &&
      /\b(error|failed|failure|exception|no such file|not found)\b/i.test(e.text || e.excerpt || ''));
    if(!isErr) return false;
  }
  if(OPT.q){
    const hay = (e.excerpt||'') + ' ' + (e.source||'') + ' ' + (e.name||'') + ' ' + (e.text||'');
    if(OPT.regex){
      try{
        if(!new RegExp(OPT.qRaw, CFG.match_case ? '' : 'i').test(hay)) return false;
      }catch(err){ return false; }   /* a half-typed pattern matches nothing */
    }else{
      const h = CFG.match_case ? hay : hay.toLowerCase();
      if(h.indexOf(OPT.q) < 0) return false;
    }
  }
  return true;
}

function resetFilters(){
  OPT = {q:'', qRaw:'', regex:false, tool:'', minTok:0, noinject:false, err:false,
         lastTurn:false, hidden:(CFG.hidden_sources||[]).concat(CFG.hide_sources||[])};
  FILTER = [];
  $('#oq').value = ''; $('#otool').value = ''; $('#otok').value = '';
  $('#onoinject').checked = false; $('#oerr').checked = false; $('#oerr2').checked = false;
  $$('[data-src-filter]').forEach(x=>x.setAttribute('aria-pressed',
    String((x.dataset.srcFilter||'') === '')));
  syncFlow(); applyFilter();
}

/* Rebuild the flow only when the render scope changes. Re-rendering the whole
   session on every keystroke would be the one visible stutter. */
function syncFlow(){
  const need = activeOpts() || SHOW_ALL;
  const changed = need !== FULL;
  FULL = need;
  /* The timeline cannot hide a filtered-out span the way the flow hides a step:
     the bars are positioned against the turn's real clock, so removing one has
     to leave the gap where it was. That means rebuilding, and it means every
     filter change rebuilds rather than only a FULL-scope one. */
  if(VIEW === 'timeline') renderWaterfall(false, 0);
  else if(changed){
    if(VIEW === 'flow') renderFlow(false, 0);
    else renderTable(false, 0);
  }
}

function applyFilter(){
  /* Counted over every event, not over the rendered rows: the flow renders
     only the tail of a long session, so counting the DOM would report "8 of
     1,625 match" when 23 events actually match. The label promises events. */
  let shown = 0;
  EVENTS.forEach((e,i)=>{ if(matches(e,i)) shown++; });

  if(VIEW === 'table'){
    let hidden = false;
    $$('#rows tr').forEach(r=>{
      if(r.classList.contains('detail')){ r.style.display = hidden ? 'none' : ''; return; }
      const i = Number(r.dataset.i);
      hidden = !matches(EVENTS[i], i);
      r.style.display = hidden ? 'none' : '';
    });
  } else {
    $$('#flow .step').forEach(el=>{
      const i = Number(el.dataset.i);
      el.style.display = matches(EVENTS[i], i) ? '' : 'none';
    });
    $$('#flow .turn').forEach(t=>{
      const steps = [...t.querySelectorAll(':scope > .steps > .step')];
      /* A turn survives when any of its steps survives, or when its own
         prompt is itself a match -- filtering to "Inputs" must show the
         prompts, and the prompt is the turn header, not a step. */
      const at = Number(t.dataset.at);
      const head = matches(EVENTS[at], at);
      const any = steps.length === 0 || steps.some(s=>s.style.display !== 'none');
      t.style.display = (any || head) ? '' : 'none';
      /* a header-only turn should not leave an empty list hanging under it */
      const ol = t.querySelector(':scope > .steps');
      if(ol) ol.style.display = any ? '' : 'none';
    });
  }

  const act = activeOpts();
  /* Counting the DOM only makes sense for the view that is on screen. The
     other two are hidden and empty, so they would report "0 rendered" while
     the view in front of you is showing exactly what you asked for. */
  let drawn = null, unit = '';
  if(VIEW === 'table'){
    drawn = $$('#rows tr.ev').filter(r=>r.style.display !== 'none').length;
    unit = ' rows';
  }else if(VIEW === 'flow'){
    drawn = $$('#flow .step').filter(s=>s.style.display !== 'none').length;
    $$('#flow .turn').forEach(t=>{
      if(t.style.display === 'none') return;
      const at = Number(t.dataset.at);
      if(matches(EVENTS[at], at)) drawn++;
    });
    unit = ' rendered';
  }else{
    drawn = $$('#wf .wfseg').length;
    unit = ' bars';
  }
  const cap = (drawn != null && drawn < shown)
    ? ' · '+drawn.toLocaleString()+unit+' drawn' : '';
  $('#filtcount').textContent = act
    ? shown.toLocaleString()+' of '+EVENTS.length.toLocaleString()+' events match'+cap
    : 'no filters active · '+EVENTS.length.toLocaleString()+' events';
  /* A filter is exactly what "the view" means to an export, so the preview
     goes stale the moment this runs. */
  previewSoon();
}

/* ------------------------------------------------------------- interaction */
/* The three views share one panel, so their visibility (and the hint that
   explains the one on screen) is set in a single place -- otherwise the
   initial render leaves two of them stacked on top of each other. */
function syncViewChrome(){
  $$('[data-view]').forEach(b=>b.setAttribute('aria-pressed',
    String(b.dataset.view===VIEW)));
  $('#flow').hidden = VIEW!=='flow';
  $('#tablewrap').hidden = VIEW!=='table';
  $('#wfwrap').hidden = VIEW!=='timeline';
  $('#viewhint').textContent = VIEW==='timeline'
    ? 'one bar per measured span · newest turn first'
    : VIEW==='flow' ? 'click any step to expand · tool calls nest their result'
    : 'one row per event';
}

function setView(v){
  VIEW = v;
  SHOWN = 0; NTURNS = 0;
  syncViewChrome();
  if(v==='timeline') renderWaterfall(false, 0);
  else if(v==='flow') renderFlow(false, 0);
  else renderTable(false, 0);
  applyFilter();
}

document.addEventListener('click', ev => {
  const seg = ev.target.closest('[data-view]');
  if(seg){ setView(seg.dataset.view); return; }

  /* Dropdowns first: a click inside a panel must not be read as a click
     outside it, which would shut the panel on the control you just used. */
  const ddb = ev.target.closest('[data-dd]');
  if(ddb){
    const p = $('#'+ddb.dataset.dd+'-p');
    const reopen = !!p && p.hidden;
    $$('.dd-p').forEach(x => { x.hidden = true; });
    $$('[data-dd]').forEach(x => x.setAttribute('aria-expanded','false'));
    openDD(ddb.dataset.dd, reopen);
    return;
  }
  if(!ev.target.closest('.dd-p')) openDD('dd-src', false);

  if(ev.target.closest('[data-src-clear]')){
    FILTER = [];
    syncFilterButtons(); syncFlow(); applyFilter();
    return;
  }
  if(ev.target.closest('[data-settings-open]')){ openSettings(true); return; }
  if(ev.target.closest('[data-page="export"]')){
    openExport($('#export').hidden);
    return;
  }
  if(ev.target.closest('[data-export]')){ exportNow(); return; }

  /* A trace opens its detail sidebar; so does its lane label, which is the
     easy thing to hit when the bar is a tenth of a percent wide. */
  const ins = ev.target.closest('[data-inspect]');
  if(ins){
    const [ia, ib] = (ins.dataset.inspect||'').split(',').map(Number);
    showInspect(ia, Number.isFinite(ib) ? ib : null);
    tipHide();
    return;
  }
  if(ev.target.closest('[data-inspect-close]')){ openInspect(false); return; }
  if(ev.target.closest('#inspect-jump')){
    if(inspectIdx != null) jumpTo(inspectIdx);
    return;
  }

  if(ev.target.closest('[data-adv]')){
    const b = ev.target.closest('[data-adv]');
    const box = $('#opts');
    box.hidden = !box.hidden;
    b.setAttribute('aria-pressed', String(!box.hidden));
    return;
  }

  if(ev.target.closest('[data-opt-reset]')){ resetFilters(); return; }

  if(ev.target.closest('[data-stop]')){ stopServer(); return; }

  /* --- settings, which is its own page now --- */
  if(ev.target.closest('[data-settings]')){
    openSettings($('#settings').hidden);
    return;
  }

  const blk = ev.target.closest('[data-jump]');
  if(blk){ jumpTo(Number(blk.dataset.jump)); return; }

  if(ev.target.closest('[data-show-all]')){
    SHOW_ALL = true;
    renderFlow(false, 0);
    if(activeOpts()) applyFilter();
    return;
  }

  const p = ev.target.closest('[data-src-filter]');
  if(p){
    const f = p.dataset.srcFilter || '';
    if(!f){
      FILTER = [];   /* "All" clears the set */
    }else{
      const at = FILTER.indexOf(f);
      if(at >= 0) FILTER.splice(at, 1);
      else FILTER.push(f);
    }
    syncFilterButtons();
    syncFlow(); applyFilter();
    return;
  }


  const step = ev.target.closest('.step');
  if(step){ openStep(step); return; }

  const tr = ev.target.closest('tr.ev');
  if(tr){
    const next = tr.nextElementSibling;
    if(next && next.classList.contains('detail')){ next.remove(); return; }
    const e = EVENTS[Number(tr.dataset.i)]||{};
    const row = document.createElement('tr');
    row.className = 'detail';
    row.innerHTML = '<td colspan="'+(TCOLS.length || 4)+'">'+
      (e.source==='tool call' ? jsonHTML(e.text||'') : '<pre>'+escTxt(e.text||e.excerpt||'')+'</pre>')+
      '</td>';
    tr.after(row);
    return;
  }

  const b = ev.target.closest('#sess button');
  if(b) load(b.dataset.id);
});

$('#search').addEventListener('input', renderSessions);
$('#folder').addEventListener('change', renderSessions);

/* Escape is handled once, in the settings block, where it also knows about the
   custom dropdowns -- two handlers for one key is how Escape ends up closing
   something you were not looking at. */

/* Tracking options. Text inputs are debounced -- re-filtering every event on
   each keystroke is the one thing here that could stutter on a long session. */
let optTimer = null;
const optSoon = () => { clearTimeout(optTimer); optTimer = setTimeout(readOpts, 140); };
function readOpts(){
  const raw = ($('#oq').value||'').trim();
  OPT = {
    q: CFG.match_case ? raw : raw.toLowerCase(),
    qRaw: raw,
    regex: CFG.match_regex === true,
    tool: ($('#otool').value||'').trim().toLowerCase(),
    minTok: Math.max(0, Number($('#otok').value)||0),
    noinject: $('#onoinject').checked,
    err: $('#oerr').checked,
    lastTurn: $('#oerr2').checked,
    hidden: (CFG.hidden_sources||[]).concat(CFG.hide_sources||[]),
  };
  /* Never leave a filter running behind a collapsed panel -- an invisible
     filter that silently hides events is worse than a noisy one. */
  if(anyAdvOpt() && $('#opts').hidden){
    $('#opts').hidden = false;
    $('[data-adv]').setAttribute('aria-pressed','true');
  }
  syncFlow(); applyFilter();
}

function anyAdvOpt(){
  return !!(OPT.q || OPT.tool || OPT.minTok || OPT.noinject || OPT.err || OPT.lastTurn);
}
$('#oq').addEventListener('input', optSoon);
$('#otool').addEventListener('input', optSoon);
$('#otok').addEventListener('input', optSoon);
['#onoinject','#oerr','#oerr2'].forEach(s =>
  $(s).addEventListener('change', readOpts));

function load(id){
  document.body.dataset.session = id;
  /* Switching session with "remember filters" off is the only moment the
     filters can be dropped safely: they were set against the session being
     left, and a source prefix that matched nothing there would silently
     filter the new one down to an empty page. */
  if(CFG.remember_filters === false) resetFilters();
  fetch('/api/state?session='+encodeURIComponent(id))
    .then(r=>r.json()).then(s=>{ apply(s,false); })
    .catch(()=>{});
}

function apply(state, append){
  STATE = Object.assign(STATE, state);
  EVENTS = append ? EVENTS.concat(state.events||[]) : (state.events||[]).slice();
  /* A session left open for hours accumulates every event it ever saw. The cap
     drops the oldest from the browser only -- the transcript on disk is
     untouched, and a reload brings them back. */
  const cap = Math.max(500, Number(CFG.max_events) || 20000);
  if(EVENTS.length > cap) EVENTS = EVENTS.slice(EVENTS.length - cap);
  RESULT_OF = pairResults(EVENTS);
  CALL_OF = {};
  Object.keys(RESULT_OF).forEach(c => { CALL_OF[RESULT_OF[c]] = Number(c); });
  const from = append ? SHOWN : 0;
  renderHead(); renderStatus(); renderFolders(); renderSessions();
  renderStats(); renderSpark(); renderSrcMenu();
  syncViewChrome();
  if(VIEW==='timeline') renderWaterfall(append, from);
  else if(VIEW==='flow') renderFlow(append, from);
  else renderTable(append, from);
  applyFilter();
  if(append && CFG.auto_follow === true) window.scrollTo(0, document.body.scrollHeight);
  if(!append)
    $('#sess').querySelector('[aria-current=true]')?.scrollIntoView({block:'nearest'});
}

/* Stopping the server from the page. The custom header is what makes this
   safe to expose: a cross-origin caller would need a preflight the server
   never approves, so a stray page cannot kill the dashboard. */
function stopServer(){
  const btn = document.querySelector('[data-stop]');
  if(!STATE.live){
    btn.textContent = '■ not served';
    return;
  }
  btn.disabled = true; btn.textContent = '■ stopping…';
  fetch('/api/shutdown', {method:'POST', headers:{'X-Trajectory':'stop'}})
    .then(()=>{
      STATE.live = false;
      document.querySelector('#live').className = 'live';
      document.querySelector('#live span:last-child').textContent = 'stopped';
      btn.textContent = '■ stopped';
      btn.title = 'Restart with: python3 ' + (STATE.script_path || 'trajectory.py') + ' serve';
    })
    .catch(()=>{
      btn.disabled = false;
      btn.textContent = '■ stop failed';
    });
}

/* Live tracing: pull only the events we do not already have. The server is
   polled, not pushed to -- a static file cannot do this at all. */
let busy = false;
function poll(){
  if(busy || !STATE.live || !CFG.live) return;
  busy = true;
  const sid = document.body.dataset.session;
  fetch('/api/state?session='+encodeURIComponent(sid)+'&after='+EVENTS.length)
    .then(r=>r.json()).then(s=>{
      if(s.session===sid && STATE.session===sid) apply(s,true);
      busy = false;
    }).catch(()=>{ busy = false; });
}

/* --------------------------------------------------------------- settings */
/* SPEC and CFG arrive from the server (trajectory.py's CONFIG_SPEC), so there
   is one definition of every knob rather than a browser copy and a Python copy
   that drift apart. Nothing here is decorative: every entry is read by
   applyCfg(), applyVars(), or the launcher -- a knob wired to nothing would not
   be in the list at all.

   Three scopes, because claiming otherwise would be a lie:
     live     the page reacts as you turn it
     open     baked in when a page loads (a "default", not a live filter)
     restart  read once by serve(), so it lands next time you start it

   Two of those need no code here at all, and say so in the spec:
     cssvar + unit   written to :root, and the stylesheet does the rest
     attr            written to body[data-*], and the stylesheet does the rest
   Everything else is dispatched explicitly below. */
const SPEC = (window.__TRAJECTORY__ && window.__TRAJECTORY__.config_spec) || [];
let CFG = Object.assign({}, (window.__TRAJECTORY__ && window.__TRAJECTORY__.config) || {});
const CFG_DEF = {};
SPEC.forEach(s => { CFG_DEF[s.k] = s.d; });
const SCOPE_BADGE = {open: 'on open', restart: 'on restart'};
const CFG_MSG = {saved: 'saved', unsaved: 'not served — local only',
                 failed: 'save failed', saving: 'saving…'};
const GROUP_ORDER = [];
SPEC.forEach(s => { if(GROUP_ORDER.indexOf(s.g) < 0) GROUP_ORDER.push(s.g); });

function cfgSpec(k){ return SPEC.find(s => s.k === k); }

/* A config written before a knob existed must read as that knob's default, not
   as `undefined` -- otherwise adding a setting would silently turn off every
   feature whose value the old file happens not to contain. */
function C(k){
  const v = CFG[k];
  if(v === undefined || v === null){ const s = cfgSpec(k); return s ? s.d : undefined; }
  return v;
}
const N = k => Number(C(k));
const B = k => C(k) !== false;

/* Arriving events are tinted; a dashboard left open all day should not blink
   at you forever, so it is a knob rather than a rule. */
function flashOn(){ return B('motion'); }

let pollTimer = null;
function syncPollTimer(){
  if(pollTimer){ clearInterval(pollTimer); pollTimer = null; }
  const ms = Math.max(500, Math.min(60000, Number(C('poll_ms')) || 2000));
  if(STATE.live && CFG.live) pollTimer = setInterval(poll, ms);
}

/* The declarative half: values that reach the page as a value. A colour knob
   and the rule that paints with it are one line apart in the spec, and changing
   the colour moves every place that reads the variable -- which is the reason
   the page reads variables rather than computing colours in JavaScript. */
function applyVars(){
  const root = document.documentElement.style;
  SPEC.forEach(s => {
    if(s.cssvar) root.setProperty(s.cssvar, String(C(s.k)) + (s.unit || ''));
    if(s.attr) document.body.dataset[s.attr] = String(C(s.k));
  });
  /* two knobs whose whole effect is one rule each, without a var of their own */
  document.body.dataset.flowmeta = String(B('flow_meta'));
  document.body.dataset.wflabels = String(B('wf_labels'));
}

/* Chrome that is neither a variable nor a re-render: elements that appear or
   disappear. Kept in one place so "which control did I turn off" has one
   answer. */
function applyChrome(){
  const show = (sel, on) => { const el = $(sel); if(el) el.hidden = !on; };
  show('.logo', B('nav_brand'));
  show('#live', B('nav_live'));
  show('[data-stop]', B('nav_stop'));
  show('#dd-src', B('nav_src'));
  show('#navclock', B('nav_clock'));
  show('[data-view="timeline"]', B('nav_view_timeline'));
  show('[data-view="flow"]', B('nav_view_flow'));
  show('[data-view="table"]', B('nav_view_table'));
  show('#folder', B('sess_folders'));
  show('[data-page="export"]', B('nav_export'));
  show('#billedpanel', B('show_billed'));
  const sb = $('.sparkbox'); if(sb) sb.hidden = !B('show_spark');
  const j = $('#inspect-jump'); if(j) j.hidden = !B('inspect_jump') || inspectIdx == null;
  tickClock();
}

let clockTimer = null;
function tickClock(){
  const el = $('#navclock');
  if(!el) return;
  clearInterval(clockTimer); clockTimer = null;
  if(!B('nav_clock')){ el.textContent = ''; return; }
  const t = () => { el.textContent = new Date().toTimeString().slice(0, 8); };
  t();
  clockTimer = setInterval(t, 1000);
}

/* Push the current CFG at everything it governs. `prev` is the config as it
   was a moment ago.

   The knobs that need no code (cssvar/attr) are applied by applyVars(). Of the
   rest, the ones that change *geometry or content* are re-rendered together
   rather than diffed one by one: a signature over exactly those keys decides
   whether anything has to be rebuilt, so a turn of a colour knob costs nothing
   while a turn of a row height rebuilds once. */
let CFG_SIG = null;
function cfgSig(){
  return SPEC.filter(s => s.scope === 'live' && !s.cssvar && !s.attr)
    .map(s => s.k + '=' + JSON.stringify(CFG[s.k]) + ',').join('');
}

function applyCfg(prev){
  applyVars();
  syncPollTimer();

  WF_TURNS = Math.max(1, Math.min(400, N('waterfall_turns') || 12));
  WF_SEG_CAP = Math.max(50, Math.min(5000, N('waterfall_segments') || 900));
  WF_MIN = Math.max(0.02, Math.min(2, N('wf_min_pct') || 0.12));
  WF_TICKS = Math.max(2, Math.min(11, N('wf_ticks') || 5));
  WF_LABELS = B('wf_labels');
  WF_HEADER = B('wf_header');
  STEP_BUDGET = Math.max(20, Math.min(2000, N('flow_budget') || 160));
  STEP_CAP = Math.max(5, Math.min(1000, N('flow_steps') || 60));
  STEP_CAP_OLD = Math.max(5, Math.min(500, N('flow_step_cap') || 60));
  OPT.hidden = (C('hidden_sources') || []).concat(C('hide_sources') || []);

  applyChrome();
  const sig = cfgSig();
  const changed = sig !== CFG_SIG;
  CFG_SIG = sig;

  if(prev && prev.default_view !== CFG.default_view){
    /* Jump only if the view on screen *was* the default being replaced --
       otherwise turning this knob would yank you out of where you are. */
    if(['timeline','flow','table'].indexOf(CFG.default_view) >= 0 &&
       prev.default_view === VIEW) VIEW = CFG.default_view;
  }
  if(changed && STATE.session){
    renderSessions(); renderStats(); renderSpark();
    syncViewChrome(); setView(VIEW);
  }
  previewSoon();
  if(!prev) return;
}

/* The Extract page's preview is derived from the same events the dashboard is
   showing, so anything that can change either -- a knob, a filter, a new poll
   -- has to invalidate it. Rebuilding the whole body per keystroke would
   stutter on a long session, hence the delay. */
let exTimer = null;
function previewSoon(){
  const page = $('#export');
  if(!page || page.hidden) return;
  clearTimeout(exTimer);
  exTimer = setTimeout(updateExportPreview, 120);
}

/* The open-scope settings are defaults applied once, before the first render.
   Routing them through applyCfg would make them live filters competing with
   the nav buttons, which is a different (and more confusing) feature. */
function initFromCfg(){
  if(['timeline','flow','table'].indexOf(C('default_view')) >= 0) VIEW = C('default_view');
  if(C('start_filter')) FILTER = [String(C('start_filter'))];
  OPT.minTok = Math.max(0, Number(C('min_tokens')) || 0);
  OPT.err = C('only_errors') === true;
  OPT.lastTurn = C('only_inflight') === true;
  OPT.hidden = (C('hidden_sources') || []).concat(C('hide_sources') || []);
  const ev = $('#oerr'); if(ev) ev.checked = OPT.err;
  const lv = $('#oerr2'); if(lv) lv.checked = OPT.lastTurn;
  const tv = $('#otok'); if(tv) tv.value = OPT.minTok || '';
  if(anyAdvOpt() && $('#opts').hidden){
    $('#opts').hidden = false;
    $('[data-adv]').setAttribute('aria-pressed', 'true');
  }
  renderSrcMenu();
  applyCfg(null);
}

/* --- sources dropdown ----------------------------------------------------
   A chip is a source prefix, so a chip and a built-in quick filter are the
   same kind of thing by the time the click handler sees them: both are just
   entries in FILTER. */
const SRC_PRESETS = [
  {v:'',             label:'Everything', note:'clear every source filter'},
  {v:'user prompt',  label:'Inputs'},
  {v:'text',         label:'Outputs'},
  {v:'tool call',    label:'Tool calls'},
  {v:'tool result',  label:'Results'},
  {v:'reasoning',    label:'Reasoning'},
  {v:'inject:',      label:'Injections'},
  {v:'system:',      label:'System'}
];

function srcItemHTML(v, label, count, chip){
  const on = v ? FILTER.indexOf(v) >= 0 : FILTER.length === 0;
  const sw = v
    ? '<i class="sw" style="background:'+hueColor(v)+'"></i>'
    : '<i class="sw"></i>';
  return '<button class="dd-i" data-src-filter="'+esc(v)+'" aria-pressed="'+on+'"'+
    (chip != null ? ' data-chip="'+esc(label)+'"' : '')+
    ' title="'+esc(v ? 'source starts with: '+v : 'clear every source filter')+'">'+
    sw+'<span class="n">'+esc(label)+'</span>'+
    (count != null ? '<span class="c">'+human(count)+'</span>' : '')+
    (chip != null ? '<span class="x" data-chip-del="'+chip+'" title="Delete this chip">✕</span>' : '')+
    '</button>';
}

function renderSrcMenu(){
  const p = $('#dd-src-p');
  if(!p) return;
  const tok = {};
  (STATE.summary||[]).forEach(x => { tok[x.source] = x.tokens; });

  let h = '<p class="dd-h">Quick filters</p>';
  SRC_PRESETS.forEach(x => { h += srcItemHTML(x.v, x.label, null); });

  /* Sources not already covered by a preset -- the preset prefix is what
     would match them, so listing both would be two controls for one thing. */
  const named = (STATE.summary||[]).map(x => x.source)
    .filter(s => !SRC_PRESETS.some(p2 => p2.v && s.indexOf(p2.v) === 0));
  if(named.length){
    h += '<div class="dd-sep"></div><p class="dd-h">Every source</p>';
    named.forEach(s => { h += srcItemHTML(s, s, tok[s]); });
  }

  const chips = CFG.chips || [];
  if(chips.length){
    h += '<div class="dd-sep"></div><p class="dd-h">Saved chips</p>';
    chips.forEach((c,i) => { h += srcItemHTML(c.prefix, c.label, null, i); });
  }

  h += '<div class="dd-f">'+
    '<button class="pill" data-src-clear>Clear filters</button>'+
    '<span class="spacer"></span>'+
    '<button class="pill" data-settings-open>All settings…</button></div>';
  p.innerHTML = h;
  syncFilterButtons();
}

/* One source of truth for which filter entries look pressed -- otherwise a
   filter set from the config file (or a chip added later) shows as off while
   it is quietly doing something. */
function syncFilterButtons(){
  $$('[data-src-filter]').forEach(x => {
    const xf = x.dataset.srcFilter || '';
    const on = xf ? FILTER.indexOf(xf) >= 0 : FILTER.length === 0;
    x.setAttribute('aria-pressed', String(on));
  });
  const l = $('#src-label');
  if(l) l.textContent = FILTER.length ? 'Sources · '+FILTER.length : 'Sources';
  const b = $('[data-dd="dd-src"]');
  if(b) b.setAttribute('aria-pressed', String(FILTER.length > 0));
}

function openDD(id, open){
  const p = $('#'+id+'-p'), b = $('[data-dd="'+id+'"]');
  if(!p) return;
  const on = open == null ? p.hidden : !!open;
  p.hidden = !on;
  if(b) b.setAttribute('aria-expanded', String(on));
}

/* Every page that carries spec controls carries the same save indicator, so a
   save is reported wherever you happen to be looking. */
let cfgSavedTimer = null;
function flashSaved(kind){
  const els = $$('.cfg-saved');
  if(!els.length) return;
  els.forEach(el => {
    el.textContent = CFG_MSG[kind] || kind;
    el.classList.add('on');
  });
  clearTimeout(cfgSavedTimer);
  cfgSavedTimer = setTimeout(
    () => els.forEach(el => el.classList.remove('on')), 1500);
}

/* Writes go to the server so a reload keeps them. On a static export there is
   nowhere to write, and saying "saved" there would be a lie -- hence the
   STATE.live check rather than an optimistic message. */
let cfgWriteTimer = null;
function persist(patch, immediate){
  clearTimeout(cfgWriteTimer);
  if(!STATE.live){ flashSaved('unsaved'); return; }
  flashSaved('saving');
  cfgWriteTimer = setTimeout(() => {
    fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Trajectory': 'stop'},
      body: JSON.stringify(patch),
    }).then(r => r.ok ? r.json() : Promise.reject(new Error('http')))
      .then(c => {
        /* The server coerces: an out-of-range number comes back clamped, and
           echoing that back is how the field shows the value that was kept. */
        const prev = Object.assign({}, CFG);
        CFG = Object.assign({}, CFG, c);
        applyCfg(prev);
        renderSettings();
        flashSaved('saved');
      })
      .catch(() => flashSaved('failed'));
  }, immediate ? 0 : 350);
}

function setCfg(k, v, opts){
  const prev = Object.assign({}, CFG);
  CFG[k] = v;
  applyCfg(prev);
  markRow(k);
  persist({[k]: v}, opts && opts.immediate);
}

/* ---------------------------------------------------------------------------
   The settings page.

   A drawer over the dashboard stopped working at this size: a hundred-odd
   knobs across sixteen groups became a scroll inside a scroll, and the thing
   the knobs are meant to *move* was hidden behind them. It is a page with a
   category rail and a search box instead, and it keeps the nav so the way back
   is always in the same place.

   Controls are rendered from the spec: a knob's type decides its control, so a
   new setting gets a working control without a line of UI code. */

let SETQ = '';        /* the search box */
let SETONLY = false;  /* only show what differs from the default */
let SETCAT = GROUP_ORDER[0] || '';

function setMatch(s){
  if(SETONLY && String(C(s.k)) === String(s.d)) return false;
  if(!SETQ) return true;
  const hay = (s.l + ' ' + s.k + ' ' + s.g + ' ' + (s.h||'') + ' ' + s.t).toLowerCase();
  return hay.indexOf(SETQ) >= 0;
}

/* --- controls ------------------------------------------------------------ */

function csHTML(k, val, opts){
  return '<div class="cs" data-cs="'+k+'">'+
    '<button class="cs-b" type="button" data-cs-b="'+k+'" aria-haspopup="listbox"'+
      ' aria-expanded="false"><span class="v">'+esc(val)+'</span>'+
      '<span class="caret">▾</span></button>'+
    '<div class="cs-p" data-cs-p="'+k+'" role="listbox" hidden>'+
      opts.map(o => '<button class="cs-i" type="button" role="option"'+
        ' data-cs-pick="'+k+'" data-val="'+esc(o)+'"'+
        ' aria-selected="'+(o === val)+'">'+
        '<span class="tick">'+(o === val ? '✓' : '')+'</span>'+
        '<span class="t">'+esc(o)+'</span></button>').join('')+
    '</div></div>';
}

function ledHTML(k){
  const items = CFG[k] || [];
  return '<div class="led" data-led="'+k+'">'+
    (items.length
      ? items.map((v,i) => '<span class="chip"><b>'+esc(v)+'</b>'+
          '<button data-led-del="'+k+'" data-i="'+i+'" title="Remove">✕</button></span>').join('')
      : '<span class="hint">none</span>')+
    '<div class="led-add"><input class="input" data-led-in="'+k+
      '" placeholder="add a value…" autocomplete="off">'+
    '<button class="pill" data-led-add="'+k+'">Add</button></div>'+
  '</div>';
}

/* The switch, not a checkbox with a tick: a two-position control whose state is
   legible at a glance across a page of forty of them. */
function ctlHTML(s){
  const v = C(s.k);
  if(s.t === 'bool')
    return '<button class="sw2" type="button" role="switch" data-set="'+s.k+'"'+
      ' aria-checked="'+(v ? 'true' : 'false')+'" aria-label="'+esc(s.l)+'"></button>';
  if(s.t === 'enum')
    return csHTML(s.k, v, s.opts);
  if(s.t === 'color')
    return '<span class="colwrap">'+
      '<input class="swatch" type="color" data-set="'+s.k+'" value="'+esc(v)+'"'+
        ' aria-label="'+esc(s.l)+'">'+
      '<input class="input cfg-num" data-set="'+s.k+'" value="'+esc(v)+'"'+
        ' spellcheck="false" autocomplete="off" style="width:96px"></span>';
  if(s.t === 'int' || s.t === 'float'){
    const step = s.step || (s.t === 'int' ? 1 : 0.01);
    return '<span class="numwrap">'+
      '<input class="rng" type="range" data-set="'+s.k+'" min="'+s.min+'" max="'+s.max+
        '" step="'+step+'" value="'+esc(String(v))+'" aria-label="'+esc(s.l)+'">'+
      '<input class="input cfg-num" type="number" data-set="'+s.k+'" value="'+esc(String(v))+
        '" min="'+s.min+'" max="'+s.max+'" step="'+step+'"></span>';
  }
  if(s.t === 'list') return ledHTML(s.k);
  return '<input class="input cfg-num wide" data-set="'+s.k+'" value="'+esc(String(v))+
    '" spellcheck="false" autocomplete="off">';
}

function setRowHTML(s){
  const changed = String(C(s.k)) !== String(s.d);
  return '<div class="set-row'+(changed ? ' changed' : '')+'" data-row="'+s.k+'">'+
    '<div class="set-l"><span class="t">'+esc(s.l)+'</span>'+
      '<span class="k">'+esc(s.k)+'</span>'+
      '<p class="h">'+esc(s.h||'')+'</p></div>'+
    '<div class="set-c">'+ctlHTML(s)+
      (SCOPE_BADGE[s.scope] ? '<span class="cfg-badge" title="takes effect '+
        esc(SCOPE_BADGE[s.scope])+'">'+esc(SCOPE_BADGE[s.scope])+'</span>' : '')+
      (changed ? '<button class="cfg-undo" data-set-undo="'+s.k+
        '" title="Back to '+esc(String(s.d))+'">↺</button>' : '')+
    '</div></div>';
}

/* --- chips: the one list-shaped setting that is its own editor ------------ */
function chipsGroupHTML(){
  const chips = CFG.chips || [];
  const list = chips.length
    ? '<div class="chips">'+chips.map((c, i) =>
        '<span class="chip"><b>'+esc(c.label)+'</b><i>'+esc(c.prefix)+'</i>'+
        '<button data-chip-del="'+i+'" title="Remove this filter">✕</button></span>').join('')+'</div>'
    : '<p class="cfg-empty">No saved filters yet.</p>';
  return '<div class="set-row" data-row="chips"><div class="set-l">'+
    '<span class="t">Saved source filters</span>'+
      '<span class="k">chips</span>'+
    '<p class="h">Your own buttons in the Sources menu. The prefix matches the '+
      'start of a source name — <b>tool call</b>, <b>inject:file</b>, <b>reasoning</b>.</p></div>'+
    '<div class="set-c" style="display:block">'+list+
    '<div class="led-add"><input class="input" id="chipLabel" placeholder="label" '+
      'maxlength="24" autocomplete="off"><input class="input" id="chipPrefix" '+
      'placeholder="source prefix" maxlength="40" autocomplete="off">'+
    '<button class="pill" data-chip-add>Add</button></div></div></div>';
}

function renderSettings(){
  const rail = $('#setrail'), body = $('#setbody');
  if(!rail || !body) return;

  const hits = {};
  SPEC.forEach(s => { if(setMatch(s)) hits[s.g] = (hits[s.g]||0)+1; });

  rail.innerHTML =
    '<input class="input" id="setsearch" placeholder="Search settings…" '+
      'autocomplete="off" value="'+esc(SETQ)+'">'+
    '<label class="chk" style="margin-bottom:9px"><input type="checkbox" id="setonly"'+
      (SETONLY ? ' checked' : '')+'><span>Changed only</span></label>'+
    GROUP_ORDER.map(g => '<button class="set-cat" data-set-cat="'+esc(g)+'"'+
      ' aria-current="'+(g === SETCAT && !SETQ)+'">'+
      '<span class="n">'+esc(g)+'</span>'+
      '<span class="c'+((hits[g]||0) ? ' hit' : '')+'">'+(hits[g]||0)+'</span>'+
    '</button>').join('')+
    '<p class="set-note" style="margin-top:14px">'+
      SPEC.length+' settings in '+GROUP_ORDER.length+' groups</p>'+
    '<button class="pill" data-set-reset>Reset all</button> '+
    '<button class="pill" data-set-close>Back to the session</button>';

  const groups = GROUP_ORDER.filter(g => hits[g]).map(g =>
    '<section class="set-g" id="setg-'+esc(g).replace(/[^a-z0-9]+/gi,'-')+'">'+
      '<h3>'+esc(g)+'</h3>'+
      SPEC.filter(s => s.g === g && setMatch(s)).map(setRowHTML).join('')+
    '</section>');
  if(!SETQ && !SETONLY) groups.push('<section class="set-g"><h3>Filters</h3>'+chipsGroupHTML()+'</section>');
  body.innerHTML = groups.join('') ||
    '<p class="set-empty">Nothing matches “'+esc(SETQ)+'”.</p>';

  const p = $('#setpath');
  if(p) p.textContent = 'stored in ' + (STATE.config_path ||
    'trajectory.config.json') +
    (STATE.live ? '' : ' · not served, so changes stay in this tab');
}

/* Rebuilding the row under a focused caret would eat what you are typing, so a
   row being edited is left alone and re-rendered when you leave it. A row that
   is already gone -- a save landed first and re-rendered the page -- throws on
   outerHTML rather than doing nothing, so the connection is checked. */
function markRow(k){
  const s = cfgSpec(k);
  if(!s) return;
  document.querySelectorAll('[data-row="'+k+'"]').forEach(row => {
    if(row.parentNode) row.outerHTML = setRowHTML(s);
  });
}

/* Showing a page and putting it in the address bar are two different jobs.
   showPage() only moves the DOM; openPage() records the move in history and
   the router below replays it. Keeping them apart is what makes Back work
   without the router and the history writing each other in a loop. */
function showPage(name){
  const s = $('#settings'), e = $('#export');
  if(!s || !e) return;
  s.hidden = name !== 'settings';
  e.hidden = name !== 'export';
  $('.shell').hidden = name !== '';
  document.body.classList.toggle('pageopen', name !== '');
  const sb = $('[data-settings]');
  if(sb) sb.setAttribute('aria-pressed', String(name === 'settings'));
  const eb = $('[data-page="export"]');
  if(eb) eb.setAttribute('aria-pressed', String(name === 'export'));
  if(name === 'settings'){ SETCAT = SETCAT || GROUP_ORDER[0] || ''; renderSettings(); }
  if(name === 'export') renderExport();
  /* Only ever one full-screen page at a time, and never a stale dropdown or
     tooltip floating over it. */
  closeCS();
  tipHide();
  if(name) window.scrollTo(0, 0);
}

function pageName(){
  return $('#settings').hidden ? ($('#export').hidden ? '' : 'export') : 'settings';
}

function openPage(name){
  if(pageName() === name) return;
  showPage(name);
  const want = name ? '#'+name : '#';
  if(location.hash !== want){
    try{ history.pushState(null, '', want); }
    catch(e){ location.hash = want; }   /* file:// and friends */
  }
}

function openSettings(open){ openPage(open ? 'settings' : ''); }
function openExport(open){ openPage(open ? 'export' : ''); }

/* The hash is the route: a link to #export opens the Extract page, and Back
   leaves it for the session instead of leaving the site. */
function routeFromHash(){
  const h = location.hash.replace(/^#/, '');
  showPage(h === 'settings' ? 'settings' : h === 'export' ? 'export' : '');
}
window.addEventListener('popstate', routeFromHash);
window.addEventListener('hashchange', routeFromHash);

/* --- the custom select -------------------------------------------------- */
function closeCS(except){
  $$('[data-cs-p]').forEach(p => {
    if(except && p === except) return;
    p.hidden = true;
    const b = $('[data-cs-b="'+p.dataset.csP+'"]');
    if(b) b.setAttribute('aria-expanded','false');
  });
}
function openCS(p){
  const b = $('[data-cs-b="'+p.dataset.csP+'"]');
  closeCS(p);
  p.hidden = !p.hidden;
  if(b) b.setAttribute('aria-expanded', String(!p.hidden));
}

function addChip(){
  const l = ($('#chipLabel') && $('#chipLabel').value || '').trim();
  const p = ($('#chipPrefix') && $('#chipPrefix').value || '').trim();
  if(!l || !p){ flashSaved('need a label and a prefix'); return; }
  const chips = (CFG.chips || []).concat([{label: l.slice(0, 24), prefix: p.slice(0, 40)}]);
  const prev = Object.assign({}, CFG);
  CFG.chips = chips;
  applyCfg(prev);
  renderSrcMenu();
  renderSettings();
  persist({chips}, true);
}

function delChip(i){
  const chips = (CFG.chips || []).slice();
  const gone = chips.splice(i, 1)[0];
  /* A chip that disappears while its filter is on would leave the view
     filtered by a prefix with no button to turn it off. */
  if(gone){
    const at = FILTER.indexOf(gone.prefix);
    if(at >= 0) FILTER.splice(at, 1);
  }
  CFG.chips = chips;
  applyCfg(null);
  renderSrcMenu();
  syncFlow(); applyFilter();
  renderSettings();
  persist({chips}, true);
}

function resetAllCfg(){
  const prev = Object.assign({}, CFG);
  CFG = Object.assign({}, CFG_DEF);
  CFG.chips = [];
  applyCfg(prev);
  renderSrcMenu();
  setView(VIEW);
  renderSettings();
  renderExport();
  persist({}, true);
}

/* --- the page's own events -----------------------------------------------
   Both spec-driven pages -- Settings and Extract -- carry the same controls,
   so they carry the same handlers. Binding them together is also what keeps a
   knob's behaviour from depending on which page you happened to open. */

function onCfgInput(ev){
  const led = ev.target.closest('[data-led-in]');
  if(led) return;                       /* Enter or the Add button commits it */
  const srch = ev.target.closest('#setsearch');
  if(srch){ SETQ = srch.value.trim().toLowerCase(); renderSettings();
    const box = $('#setsearch'); if(box){ box.focus(); box.setSelectionRange(box.value.length, box.value.length); }
    return; }

  const el = ev.target.closest('[data-set]');
  if(!el) return;
  const s = cfgSpec(el.dataset.set);
  if(!s) return;
  if(s.t === 'color'){
    /* one control per colour: the swatch and the hex field are the same knob,
       so typing a hex repaints immediately and dragging the swatch fixes the
       field. Both go through here. */
    const v = String(el.value||'').trim();
    document.querySelectorAll('[data-set="'+s.k+'"]').forEach(x => {
      if(x !== el) x.value = v;
    });
    if(/^#?[0-9a-f]{6}$/i.test(v)) setCfg(s.k, v.startsWith('#') ? v : '#'+v);
    return;
  }
  if(s.t === 'list'){ setCfgList(s.k, el.value); return; }
  let v = el.value;
  if(s.t === 'int' || s.t === 'float'){
    /* A half-typed "-" or "1e" is NaN; writing that would fight the caret and
       snap the field back mid-keystroke. Wait for a number that parses. */
    if(el.value === ''){ v = s.d; }
    else { v = Number(el.value); if(!isFinite(v)) return; }
    document.querySelectorAll('[data-set="'+s.k+'"]').forEach(x => {
      if(x !== el) x.value = el.value;
    });
  }
  setCfg(s.k, v);
}

function onCfgChange(ev){
  const el = ev.target.closest('[data-set]');
  if(!el) return;
  const s = cfgSpec(el.dataset.set);
  if(!s) return;
  if(s.t === 'list') return;            /* the list commits on Add/✕ */
  const v = s.t === 'int' || s.t === 'float'
    ? (el.value === '' ? s.d : Number(el.value)) : el.value;
  setCfg(s.k, v, {immediate: true});
}

['#settings','#export'].forEach(sel => {
  $(sel).addEventListener('input', onCfgInput);
  $(sel).addEventListener('change', onCfgChange);
});

['#settings','#export'].forEach(sel => {
  $(sel).addEventListener('keydown', ev => {
    if(ev.key !== 'Enter') return;
    const led = ev.target.closest('[data-led-in]');
    if(led){ ev.preventDefault(); setCfgList(led.dataset.ledIn, led.value, true); return; }
    if(ev.target.closest('#chipLabel,#chipPrefix')){ ev.preventDefault(); addChip(); }
  });
  $(sel).addEventListener('click', onCfgClick);
});

/* A list-shaped setting is committed as a whole: the input adds one entry, the
   chip's ✕ removes one, and both write the resulting list. */
function setCfgList(k, value, clear){
  const v = String(value||'').trim();
  if(!v) return;
  const s = cfgSpec(k);
  const cur = (CFG[k] || []).slice();
  if(cur.indexOf(v) < 0) cur.push(v);
  if(cur.length > 64) cur.pop();
  setCfg(k, cur, {immediate: true});
  if(clear){
    const inp = document.querySelector('[data-led-in="'+k+'"]');
    if(inp){ inp.value = ''; }
  }
  markRow(k);
}

function onCfgClick(ev){
  const cat = ev.target.closest('[data-set-cat]');
  if(cat){
    SETCAT = cat.dataset.setCat;
    const g = document.getElementById('setg-'+SETCAT.replace(/[^a-z0-9]+/gi,'-'));
    if(g) g.scrollIntoView({block:'start'});
    $$('[data-set-cat]').forEach(b => b.setAttribute('aria-current',
      String(b === cat)));
    return;
  }
  const sw = ev.target.closest('.sw2[data-set]');
  if(sw){
    const on = sw.getAttribute('aria-checked') !== 'true';
    sw.setAttribute('aria-checked', String(on));
    setCfg(sw.dataset.set, on, {immediate: true});
    return;
  }
  const csb = ev.target.closest('[data-cs-b]');
  if(csb){ openCS($('[data-cs-p="'+csb.dataset.csB+'"]')); return; }
  const pick = ev.target.closest('[data-cs-pick]');
  if(pick){
    setCfg(pick.dataset.csPick, pick.dataset.val, {immediate: true});
    closeCS();
    return;
  }
  if(!ev.target.closest('.cs')) closeCS();

  const undo = ev.target.closest('[data-set-undo]');
  if(undo){ setCfg(undo.dataset.setUndo, CFG_DEF[undo.dataset.setUndo], {immediate: true}); return; }
  const del = ev.target.closest('[data-led-del]');
  if(del){
    const k = del.dataset.ledDel, i = Number(del.dataset.i);
    const cur = (CFG[k] || []).slice();
    cur.splice(i, 1);
    setCfg(k, cur, {immediate: true});
    markRow(k);
    return;
  }
  const add = ev.target.closest('[data-led-add]');
  if(add){
    const k = add.dataset.ledAdd;
    const inp = document.querySelector('[data-led-in="'+k+'"]');
    setCfgList(k, inp && inp.value, true);
    return;
  }
  if(ev.target.closest('[data-chip-add]')){ addChip(); return; }
  const cd = ev.target.closest('[data-chip-del]');
  if(cd){ delChip(Number(cd.dataset.chipDel)); return; }
  if(ev.target.closest('[data-set-reset]')){ resetAllCfg(); return; }
  if(ev.target.closest('[data-set-close]')){ openSettings(false); return; }
  const only = ev.target.closest('#setonly');
  if(only){ SETONLY = only.checked; renderSettings(); }
}
/* The "changed only" checkbox is a checkbox, so it fires change, not click. */
$('#settings').addEventListener('change', ev => {
  const only = ev.target.closest('#setonly');
  if(only){ SETONLY = only.checked; renderSettings(); }
});

/* --- keyboard ------------------------------------------------------------ */
/* Every binding is a setting, because a key that fires while you are typing
   somewhere else is worse than no key at all -- and this page has text fields
   in three places. */
function keyList(k){
  return String(C(k) || '').split(',').map(x => x.trim()).filter(Boolean);
}
document.addEventListener('keydown', ev => {
  if(ev.key === 'Escape'){
    if($('#settings') && !$('#settings').hidden){ openSettings(false); return; }
    if($('#export') && !$('#export').hidden){ openExport(false); return; }
    if(!$('#inspect').hidden){ openInspect(false); return; }
    closeCS(); tipHide();
    return;
  }
  if(!B('keys_on')) return;
  const t = ev.target;
  if(t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
  if(ev.metaKey || ev.ctrlKey || ev.altKey) return;

  const views = keyList('key_views');
  const at = views.indexOf(ev.key);
  if(at >= 0){
    const order = ['timeline','flow','table'];
    if(order[at]){ openSettings(false); setView(order[at]); }
    return;
  }
  if(ev.key === C('key_next') || ev.key === C('key_prev')){
    const dir = ev.key === C('key_next') ? 1 : -1;
    if(inspectIdx == null) return;
    ev.preventDefault();
    showInspect(inspectIdx + dir, null);
    const tr = $('#rows tr[data-i="'+(inspectIdx+dir)+'"]');
    if(tr) tr.scrollIntoView({block:'nearest'});
    return;
  }
  if(ev.key === C('key_close')){ openInspect(false); return; }
});

/* --- extract -------------------------------------------------------------
   The view on screen is usually the thing worth keeping: a filtered table is a
   question that was just answered, and the answer should leave the browser in
   the shape it was asked in. So `view` is the default scope, and the page
   shows the bytes before you commit to them. */
function exportRows(){
  const scope = C('export_scope') || 'view';
  const full = B('export_text');
  let src;
  if(scope === 'turn'){
    const turns = buildTurns(EVENTS);
    src = turns.length ? turns[turns.length-1].items.map(i => ({e: EVENTS[i], i})) : [];
  }else if(scope === 'session'){
    src = EVENTS.map((e,i) => ({e,i}));
  }else{
    src = EVENTS.map((e,i) => ({e,i})).filter(({e,i}) => matches(e,i));
  }
  return src.map(({e}) => ({
    t: e.t, ts: e.ts, source: e.source, name: e.name || undefined,
    tokens: e.tokens, error: e.error || undefined,
    text: full ? (e.text || e.excerpt) : e.excerpt,
  }));
}

/* One builder for both the download and the preview, so the preview cannot
   show something the file will not contain. */
function buildExport(){
  const fmt = C('export_format') || 'json';
  const rows = exportRows();
  let body, mime, ext = fmt;
  if(fmt === 'csv'){
    const keys = ['t','ts','source','name','tokens','error','text'];
    const cell = v => {
      const s = v == null ? '' : String(v);
      return /[",\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s;
    };
    body = keys.join(',') + '\n' + rows.map(r => keys.map(k => cell(r[k])).join(',')).join('\n');
    mime = 'text/csv';
  }else if(fmt === 'md'){
    const head = '| time | source | tool | tokens | text |\n|---|---|---|---:|---|\n';
    const cell = v => String(v == null ? '' : v).replace(/\|/g,'\\|').replace(/\n/g,' ');
    body = head + rows.map(r => '| '+cell(r.t)+' | '+cell(r.source)+' | '+cell(r.name)+
      ' | '+r.tokens+' | '+cell(r.text)+' |').join('\n');
    mime = 'text/markdown';
  }else{
    body = JSON.stringify(rows, null, 2);
    mime = 'application/json';
    ext = 'json';
  }
  if(B('export_meta')){
    const st = STATE.status || {};
    const head = ['# trajectory export',
      '#',
      '# session   ' + STATE.session,
      '# records   ' + EVENTS.length + ' loaded' + (rows.length !== EVENTS.length
        ? ', ' + rows.length + ' exported' : ''),
      '# model     ' + (st.model || 'unknown'),
      '# exported  ' + new Date().toISOString(),
      '', ''].join('\n');
    body = head + body;
  }
  const name = String(C('export_name') || 'trajectory').replace(/[^\w.-]+/g,'-') || 'trajectory';
  return {body, mime, ext, name, rows};
}

/* Bytes, not a rounded-off number: the point of the figure is to tell you
   whether this is a file you can paste into a chat or not. */
function bytesHuman(n){
  if(n < 1024) return n + ' B';
  if(n < 1024*1024) return (n/1024).toFixed(1) + ' kB';
  return (n/1048576).toFixed(2) + ' MB';
}

const EX_PREVIEW_LINES = 64;
function updateExportPreview(){
  const pre = $('#exprev'); if(!pre) return;
  if(!STATE.session){ pre.innerHTML = '<span class="ex-empty">No session loaded.</span>'; return; }
  const {body, ext, name, rows} = buildExport();
  const lines = body.split('\n');
  const cut = lines.length > EX_PREVIEW_LINES;
  /* Text nodes, so a transcript containing markup stays text. */
  pre.textContent = (cut ? lines.slice(0, EX_PREVIEW_LINES).join('\n') : body) +
    (cut ? '\n\n… ' + (lines.length - EX_PREVIEW_LINES) + ' more lines' : '');
  const size = new Blob([body]).size;
  $('#exfile').textContent = name + '.' + ext;
  $('#exsize').textContent = rows.length + ' records · ' + lines.length + ' lines · ' +
    bytesHuman(size);
}

function renderExport(){
  const b = $('#exportbody'); if(!b) return;
  b.innerHTML = '<section class="set-g">' +
    SPEC.filter(s => s.g === 'Export').map(setRowHTML).join('') +
    '</section>';
  const n = $('#exnote');
  if(n) n.textContent = STATE.session
    ? 'The file is built in this tab from the ' + EVENTS.length +
      ' records on screen — nothing is uploaded anywhere.'
    : 'Open a session first; there is nothing to extract yet.';
  updateExportPreview();
}

function openExport(open){
  const page = $('#export');
  if(!page) return;
  if(open) openSettings(false);
  page.hidden = !open;
  $('.shell').hidden = !!open;
  const b = $('[data-page="export"]');
  if(b) b.setAttribute('aria-pressed', String(!!open));
  document.body.classList.toggle('pageopen', !!open);
  if(open) renderExport();
  closeCS(); tipHide();
  if(open) window.scrollTo(0, 0);
  const want = open ? '#export' : '#';
  if(location.hash !== want){
    try{ history.replaceState(null, '', want); }catch(e){ location.hash = want; }
  }
}

function exportNow(){
  if(!STATE.session) return;
  const {body, mime, ext, name, rows} = buildExport();
  if(C('export_confirm') === true && !confirm('Write '+rows.length+' records to '+
      name+'.'+ext+'?')) return;
  const url = URL.createObjectURL(new Blob([body], {type: mime}));
  const a = document.createElement('a');
  a.href = url; a.download = name+'.'+ext;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/* The Export group of the settings page and this page are the same knobs, so a
   change made on either has to refresh both. */
function syncExport(){
  renderExport();
}

initFromCfg();
apply(window.__TRAJECTORY__||{}, false);
renderSettings();
if(location.hash === '#settings') openSettings(true);
else if(location.hash === '#export') openExport(true);
if(STATE.live) syncPollTimer();
"""


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>@@TRAJ:TITLE@@</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2032%2032'%3E%3Ccircle%20cx='16'%20cy='16'%20r='10'%20fill='%232F6F4E'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Instrument+Serif&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>@@TRAJ:CSS@@</style>
</head>
<body data-session="@@TRAJ:SESSION@@">
<div class="noise"></div>

<header class="nav">
  <div class="nav-inner">
    <a class="logo" href="#"><span class="dot"></span>Trajectory<sup>TM</sup></a>
    <span class="spacer"></span>
    <span class="seg">
      <button class="pill" data-view="timeline" aria-pressed="true">Timeline</button>
      <button class="pill" data-view="flow" aria-pressed="false">Flow</button>
      <button class="pill" data-view="table" aria-pressed="false">Table</button>
    </span>
    <span class="live @@TRAJ:LIVECLS@@" id="live"><span class="dot"></span><span>@@TRAJ:LIVELABEL@@</span></span>
    <span class="clock" id="navclock" aria-label="Local time"></span>
    <div class="dd" id="dd-src">
      <button class="pill dd-b" data-dd="dd-src" aria-expanded="false"
        aria-haspopup="true" aria-controls="dd-src-p"><span id="src-label">Sources</span>
        <span class="caret">▾</span></button>
      <div class="dd-p" id="dd-src-p" role="group" hidden></div>
    </div>
    <button class="pill" data-page="export" aria-controls="export">⤓ Extract</button>
    <button class="pill" data-settings aria-pressed="false" aria-controls="settings">⚙ Settings</button>
    <button class="pill stop" data-stop>■ Stop</button>
  </div>
</header>

<!-- Settings is a page, not a drawer: at this size the drawer became a scroll
     inside a scroll and hid the very thing the knobs are meant to move. The
     rail is the category list; everything to its right is rendered from the
     spec the server ships, so a new knob arrives with a working control. -->
<main class="set" id="settings" hidden aria-label="Settings">
  <aside class="set-rail" id="setrail"></aside>
  <div class="set-body">
    <div class="set-head">
      <h2>Settings</h2>
      <span class="spacer"></span>
      <span class="cfg-saved" id="cfgsaved">saved</span>
    </div>
    <p class="set-note" id="setpath"></p>
    <div id="setbody"></div>
  </div>
</main>

<!-- Extract is the same idea as Settings -- its own page -- for the same
     reason: choosing what to pull out of a session is a decision you make by
     looking at the result, so the result is on screen next to the choices. The
     controls are the Export group of the spec, rendered with the same widgets,
     so there is one definition of what an export option is. -->
<main class="ex" id="export" hidden aria-label="Extract">
  <div class="ex-l">
    <div class="set-head">
      <h2>Extract</h2>
      <span class="spacer"></span>
      <span class="cfg-saved" id="exsaved"></span>
    </div>
    <p class="set-note" id="exnote"></p>
    <div id="exportbody"></div>
  </div>
  <div class="ex-r">
    <div class="ex-bar">
      <span class="label" id="exfile">trajectory.json</span>
      <span class="spacer"></span>
      <span class="ex-size" id="exsize"></span>
      <button class="pill primary" data-export>⤓ Download</button>
    </div>
    <pre class="ex-prev" id="exprev" tabindex="0"></pre>
  </div>
</main>

<aside class="inspect" id="inspect" hidden aria-label="Event details">
  <div class="inspect-h">
    <p class="label" id="inspect-title">Event</p>
    <span class="spacer"></span>
    <button class="pill" id="inspect-jump" hidden>Open in table</button>
    <button class="pill" data-inspect-close aria-label="Close details">✕</button>
  </div>
  <div class="inspect-b" id="inspect-body"></div>
</aside>

<div class="tip" id="tip" role="tooltip" hidden></div>

<div class="shell">
  <aside class="side">
    <div class="side-head">
      <p class="label">Sessions</p>
      <span class="label" id="records"></span>
    </div>
    <input class="input" id="search" placeholder="Find by id, folder or project…" autocomplete="off">
    <select class="input" id="folder" aria-label="Filter by folder"></select>
    <ul class="sess" id="sess"></ul>
    <p class="label scount" id="scount"></p>
  </aside>

  <main class="main">
    <p class="crumb" id="crumb"></p>
    <h1 id="h1"></h1>
    <div class="smeta" id="smeta"></div>
    <div class="status" id="status"></div>

    <div class="panel">
      <div class="panel-h">
        <p class="label">Context by source</p>
        <span class="hint">estimated from characters</span>
      </div>
      <div class="panel-b">
        <div class="share" id="share"></div>
        <div class="legend" id="legend"></div>
        <div class="sparkbox">
          <p class="label">Volume per minute</p>
          <div id="spark"></div>
          <p class="spark-meta" id="spark-meta"></p>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-h"><p class="label">Billed by the API</p>
        <span class="hint">exact, not estimated</span></div>
      <div class="panel-b"><div class="billed" id="billed"></div></div>
    </div>

    <div class="tiles" id="tiles"></div>

    <div class="panel">
      <div class="panel-h">
        <p class="label">Tracking options</p>
        <span class="hint" id="filtcount"></span>
        <button class="pill" data-adv aria-pressed="false" aria-controls="opts">Advanced</button>
      </div>
      <div class="panel-b opts" id="opts" hidden>
        <label class="fld"><span class="label">Search text</span>
          <input class="input" id="oq" placeholder="match inside events…" autocomplete="off"></label>
        <label class="fld"><span class="label">Tool</span>
          <input class="input" id="otool" placeholder="Bash, Edit, Read…" autocomplete="off"></label>
        <label class="fld"><span class="label">Min tokens</span>
          <input class="input" id="otok" type="number" min="0" step="50" placeholder="0"></label>
        <label class="chk"><input type="checkbox" id="onoinject">
          <span>Hide injections</span></label>
        <label class="chk"><input type="checkbox" id="oerr">
          <span>Only failures</span></label>
        <label class="chk"><input type="checkbox" id="oerr2">
          <span>Only the turn in flight</span></label>
        <button class="pill" data-opt-reset>Reset filters</button>
      </div>
    </div>

    <div class="panel" style="margin-top:14px">
      <div class="panel-h">
        <p class="label">Event stream</p>
        <span class="hint" id="viewhint">click any step to expand · tool calls nest their result</span>
      </div>
      <div class="panel-b" id="wfwrap">
        <div class="wf-legend">
          <span><i class="wfseg input"></i>Input <em>waiting on the model</em></span>
          <span><i class="wfseg model"></i>Model <em>producing</em></span>
          <span><i class="wfseg tool"></i>Tools <em>running</em></span>
        </div>
        <div id="wf"></div>
      </div>
      <div id="flow"></div>
      <div class="wrap" id="tablewrap" hidden>
        <table>
          <thead><tr><th>Time</th><th>Source</th><th style="text-align:right">Tokens</th><th>Detail</th></tr></thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </div>

    <div class="foot">
      <span>sizes estimated from characters · billed usage is exact</span>
      <span>every record the model saw, by source</span>
    </div>
  </main>
</div>

<script>window.__TRAJECTORY__=@@TRAJ:STATE@@;</script>
<script>@@TRAJ:JS@@</script>
</body>
</html>
"""


MARK = "@@TRAJ:"


def render(state, live=False, title="Trajectory"):
    """Return the full dashboard document for a state dict.

    Substitutions run in one pass over namespaced markers. The state payload is
    transcript text, so it can contain anything -- including a marker, or a
    literal `</script>` that would close the tag early and take the rest of
    the page's JS with it. Both `@` and `<` are therefore escaped: neither can
    appear outside a JSON string, and both decode back to themselves, so the
    escaping cannot change the payload's structure or meaning.
    """
    import json

    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("@", "\\u0040").replace("<", "\\u003c")

    sid = state.get("session") or ""
    doc = PAGE
    for marker, value in (
        (MARK + "CSS@@", CSS),
        (MARK + "JS@@", JS),
        (MARK + "SESSION@@", sid),
        (MARK + "TITLE@@", title if not sid else f"{title} — {sid}"),
        (MARK + "LIVECLS@@", "on" if live else ""),
        (MARK + "LIVELABEL@@", "live" if live else "snapshot"),
        (MARK + "STATE@@", payload),
    ):
        doc = doc.replace(marker, value)

    leftover = doc.count(MARK)
    assert not leftover, f"unreplaced markers: {leftover}"
    return doc
