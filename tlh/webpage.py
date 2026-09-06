"""The single page tlh/web.py serves.

Kept as one string in one module on purpose: no static folder to lose, no
asset paths to get wrong, and the server stays a file you can read in one go.

The labels are Vietnamese because this page exists for the people who are not
going to read a console -- the rest of the project talks English to whoever is
editing it. English is available at a switch; see tlh/i18n.py.

The Vietnamese also stays inline in the markup below, next to its data-t key,
so the page reads correctly before the script runs and if it never runs.
"""
import json

from . import i18n

_HTML = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TieuLinh-Hota-Download-And-Cut-Video</title>
<style>
  :root {
    --bg: #14161a; --card: #1c1f25; --line: #2b3038; --ink: #e6e8ec;
    --dim: #8b93a1; --accent: #5aa9e6; --ok: #4caf82; --warn: #d9a13b;
    --bad: #d9534f;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 14px/1.5 "Segoe UI", system-ui, sans-serif; }
  .wrap { max-width: 980px; margin: 0 auto; padding: 24px 18px 60px; }
  .head { display: flex; align-items: flex-start; gap: 16px; }
  .head h1 { flex: 1; min-width: 0; }
  .langs { display: inline-flex; gap: 2px; padding: 3px; flex: none;
           background: #0e1014; border: 1px solid var(--line);
           border-radius: 8px; }
  .langs button { padding: 4px 11px; font-size: 12px; font-weight: 700;
        background: none; border: 0; color: var(--dim); border-radius: 5px; }
  .langs button:hover { color: var(--ink); background: #1a1f27; }
  .langs button.on, .langs button.on:hover { color: #0d1117;
        background: var(--accent); }
  h1 { font-size: 19px; margin: 0 0 2px; }
  h1 a { color: var(--accent); font-weight: 400; font-size: 15px;
         text-decoration: none; }
  h1 a:hover { text-decoration: underline; }
  h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .08em;
       color: var(--dim); margin: 28px 0 10px; font-weight: 600; }
  .card { background: var(--card); border: 1px solid var(--line);
          border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; }
  .drive { display: flex; align-items: center; gap: 12px; font-size: 13px; }
  .drive .bar { flex: 1; height: 8px; background: #0e1014; border-radius: 4px;
                overflow: hidden; }
  .drive .bar i { display: block; height: 100%; background: var(--accent); }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  input[type=text] { flex: 1; min-width: 260px; background: #0e1014;
       border: 1px solid var(--line); color: var(--ink); border-radius: 6px;
       padding: 9px 11px; font: inherit; }
  select, button { background: #262b33; color: var(--ink); font: inherit;
       border: 1px solid var(--line); border-radius: 6px; padding: 9px 13px;
       cursor: pointer; }
  button.go { background: var(--accent); border-color: var(--accent);
              color: #06121c; font-weight: 600; }
  button.small { padding: 5px 10px; font-size: 13px; }
  button.danger { border-color: #5a3436; color: #e08c88; }
  button.danger:hover { background: #3a2426; }
  .files { display: flex; flex-direction: column; gap: 6px; }
  .file { display: flex; align-items: center; gap: 10px; font-size: 13px; }
  .file .nm { flex: 1; overflow: hidden; text-overflow: ellipsis;
              white-space: nowrap; }
  .file .sz { color: var(--dim); font-variant-numeric: tabular-nums; }
  /* Chạy is what the row is for; Mở and Xoá only reveal or remove. Tinted
     rather than filled -- a row of solid blue buttons down the list would
     shout louder than the one real call to action at the top of the card. */
  .file button[data-run]:not(:disabled) { border-color: #35566e;
        color: #bcdcf5; }
  .file button[data-run]:not(:disabled):hover { background: #223447; }
  .job .head { display: flex; align-items: baseline; gap: 10px; }
  .job .t { flex: 1; font-weight: 600; overflow: hidden;
            text-overflow: ellipsis; white-space: nowrap; }
  .badge { font-size: 12px; padding: 2px 9px; border-radius: 20px;
           border: 1px solid var(--line); color: var(--dim);
           white-space: nowrap; }
  .badge.run { border-color: var(--accent); color: var(--accent); }
  .badge.done { border-color: var(--ok); color: var(--ok); }
  .badge.bad { border-color: var(--bad); color: var(--bad); }
  .prog { height: 6px; background: #0e1014; border-radius: 3px; margin: 10px 0 6px;
          overflow: hidden; }
  .prog i { display: block; height: 100%; background: var(--accent);
            transition: width .4s; }
  .when { color: var(--dim); font-size: 12px; margin-top: 2px;
          font-variant-numeric: tabular-nums; }
  .when b { color: var(--ink); font-weight: 600; }
  .meta { color: var(--dim); font-size: 13px; }
  .meta b { color: var(--ink); font-weight: 600; }
  .note { margin-top: 6px; font-size: 13px; }
  .note.warn { color: var(--warn); }
  .note.bad { color: var(--bad); }
  .kv { display: grid; grid-template-columns: 120px 1fr; gap: 2px 10px;
        margin-top: 8px; font-size: 13px; }
  .kv dt { color: var(--dim); }
  .kv dd { margin: 0; overflow-wrap: anywhere; }
  pre { background: #0e1014; border: 1px solid var(--line); border-radius: 6px;
        padding: 10px; max-height: 300px; overflow: auto; font-size: 12px;
        margin: 10px 0 0; white-space: pre-wrap; }
  .empty { color: var(--dim); font-size: 13px; }
  .opts { padding: 4px 6px; }
  .opt { display: flex; gap: 11px; align-items: flex-start; padding: 11px 10px;
         border-radius: 6px; cursor: pointer; }
  .opt:hover { background: #22262e; }
  .opt input { margin: 3px 0 0; accent-color: var(--accent); flex: none; }
  .opt b { display: block; font-weight: 600; }
  .opt i { display: block; color: var(--dim); font-style: normal;
           font-size: 13px; margin-top: 2px; }
  .opt em { font-style: normal; color: var(--dim); font-weight: 400;
            font-size: 12px; }
  .paths { display: grid; grid-template-columns: max-content 1fr;
           gap: 4px 14px; font-size: 12px; }
  .paths dt { color: var(--dim); }
  .paths dd { margin: 0; font-family: ui-monospace, Consolas, monospace;
              overflow-wrap: anywhere; }
  .paths dd button { margin-left: 8px; vertical-align: 1px; }
  /* One row per folder: path on the left, what is in it on the right.
     It used to stack the path above its own numbers and paint the path in
     full-strength ink while the size stayed dim -- brightest on the thing the
     reader already knows, faintest on the thing they came to read. */
  .folders { font-size: 13px; display: grid; align-items: center;
             grid-template-columns: 1fr max-content; gap: 8px 16px; }
  .folders dt { color: var(--dim); font-size: 12px; min-width: 0;
                overflow-wrap: anywhere;
                font-family: ui-monospace, Consolas, monospace; }
  .folders dd { margin: 0; display: flex; gap: 8px; align-items: center;
                color: var(--ink); font-variant-numeric: tabular-nums; }
  .sep { color: var(--dim); font-size: 13px; margin-bottom: 11px; }
  /* Spelled once, so the lines inside a card sit at the same inset and the
     same distance apart. */
  .paths, .folders, .sep, details.dev { border-top: 1px solid var(--line);
        margin-left: 0; margin-right: 0; margin-top: 14px; padding-top: 12px; }
  details.dev { margin-bottom: 2px; }
  /* The browser's own disclosure triangle, not a glyph of ours: a CSS
     escape here came out as a tofu box, and every font has this one. */
  details.dev > summary { cursor: pointer; color: var(--dim); font-size: 13px;
       padding: 10px 6px 10px 2px; user-select: none; }
  details.dev > summary:hover { color: var(--ink); }
  code { background: #0e1014; border: 1px solid var(--line); border-radius: 4px;
         padding: 1px 5px; font-size: 12px; color: var(--ink); }
  .modal { position: fixed; inset: 0; background: rgba(6, 8, 11, .78);
           display: flex; align-items: flex-start; justify-content: center;
           padding: 40px 16px; overflow: auto; z-index: 10; }
  /* display:flex above beats the browser's own [hidden] rule, which is why
     the sheet showed itself on load. Say it again, louder. */
  .modal[hidden] { display: none; }
  .sheet { background: var(--card); border: 1px solid var(--line);
           border-radius: 10px; width: 100%; max-width: 860px; }
  .sheet > .head { display: flex; gap: 10px; align-items: center;
        padding: 14px 16px; border-bottom: 1px solid var(--line);
        flex-wrap: wrap; position: sticky; top: 0; background: var(--card);
        border-radius: 10px 10px 0 0; }
  .sheet > .head .n { flex: 1; color: var(--dim); font-size: 13px; }
  .vid { display: flex; gap: 12px; padding: 12px 16px;
         border-bottom: 1px solid var(--line); align-items: flex-start; }
  .vid:last-child { border-bottom: 0; }
  .vid img { width: 160px; height: 90px; object-fit: cover; border-radius: 6px;
             background: #0e1014; flex: none; }
  .vid .body { flex: 1; min-width: 0; }
  .vid .t { font-weight: 600; overflow-wrap: anywhere; }
  .vid .m { color: var(--dim); font-size: 13px; margin-top: 3px; }
  .vid .acts { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
  .vid.live { opacity: .55; }
  button:disabled { opacity: .45; cursor: not-allowed; }
  /* Keyboard users had nothing: the browser default ring is close to
     invisible on this background. :focus-visible so a mouse click does
     not leave a ring behind it. */
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  /* This is the page's top-level choice, so it is drawn as a control rather
     than as two words with a thin line under one of them. inline-flex so the
     bar hugs the two tabs instead of running the width of the page. */
  .tabs { display: inline-flex; gap: 4px; margin: 22px 0 6px; padding: 5px;
          background: #0e1014; border: 1px solid var(--line);
          border-radius: 11px; }
  .tabs button { background: none; border: 0; color: var(--dim); font: inherit;
        font-size: 15px; font-weight: 700; letter-spacing: .2px;
        cursor: pointer; padding: 10px 22px; border-radius: 8px;
        transition: background .12s ease, color .12s ease; }
  .tabs button:hover { color: var(--ink); background: #1a1f27; }
  /* Near-black on the accent blue: the filled tab has to read as selected
     from across the room, and dark ink on that blue is what carries. */
  .tabs button.on, .tabs button.on:hover { color: #0d1117;
        background: var(--accent); box-shadow: 0 2px 10px rgba(90,169,230,.28); }
  video.prev { width: 100%; max-height: 62vh; background: #000; border-radius: 8px;
        border: 1px solid var(--line); margin: 10px 0 4px; display: block; }
  .marks { display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
           margin-top: 14px; }
  .marks.act { margin-top: 18px; }
  .marks label { color: var(--dim); font-size: 13px; }
  /* min-width and flex, not just width: the shared input[type=text] rule sets
     flex:1 and min-width:260px, and min-width beats width -- which stretched
     these two marks past the card and pushed the last button onto a line of
     its own. */
  .marks input { width: 108px; min-width: 0; flex: none; text-align: center;
                 font-family: ui-monospace, Consolas, monospace; }
  .marks .gap { flex: 1; min-width: 20px; }
  /* The controls under a paragraph need air; .row carries none of its own. */
  #tab-trim .row { margin-top: 14px; }
  .kv dd a.mail { color: var(--accent); text-decoration: none; }
  .kv dd a.mail:hover { text-decoration: underline; }
  .foot { color: var(--dim); font-size: 12px; margin-top: 26px;
          border-top: 1px solid var(--line); padding-top: 12px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <h1><span data-t="head.title">Cắt VOD stream từ kênh</span>
      <a href="https://www.youtube.com/@TieulinhHOTA" target="_blank" rel="noreferrer">https://www.youtube.com/@TieulinhHOTA</a></h1>
    <div class="langs" data-tt="lang.tip" title="Đổi ngôn ngữ giao diện">
      <button data-lang="vi" class="on">VI</button>
      <button data-lang="en">EN</button>
    </div>
  </div>

  <div class="card">
    <div class="drive">
      <span id="dv">&nbsp;</span>
      <span class="bar"><i id="dvbar" style="width:0"></i></span>
      <span id="dvfree" class="sz"></span>
    </div>
    <dl class="folders">
      <dt class="p-in">input\</dt>
      <dd><span id="szin">&mdash;</span>
        <button class="small" data-open="input" data-t="btn.open"
          data-tt="tip.openFolder"
          title="Mở thư mục này trong Explorer">Mở</button>
        <button class="small danger" data-clear="input" data-t="btn.clear"
          data-tt="tip.clearFolder"
          title="Chuyển mọi file trong thư mục này vào Thùng rác">Dọn</button></dd>
      <dt class="p-out">output\</dt>
      <dd><span id="szout">&mdash;</span>
        <button class="small" data-open="output" data-t="btn.open"
          data-tt="tip.openFolder"
          title="Mở thư mục này trong Explorer">Mở</button>
        <button class="small danger" data-clear="output" data-t="btn.clear"
          data-tt="tip.clearFolder"
          title="Chuyển mọi file trong thư mục này vào Thùng rác">Dọn</button></dd>
    </dl>
  </div>

  <div class="tabs">
    <button class="tab on" data-tab="fn" data-t="tab.fn">Chức năng</button>
    <button class="tab" data-tab="trim" data-t="tab.trim">Hỗ trợ cắt ghép</button>
    <button class="tab" data-tab="author" data-t="tab.author">Tác giả</button>
  </div>

  <div id="tab-fn">

  <h2 data-t="h2.step1">1 &middot; Chọn việc muốn làm</h2>
  <div class="card opts">
    <label class="opt"><input type="radio" name="mode" value="games" checked><span>
      <b data-t="opt.games.t">Lược bỏ thời gian chờ turn đối thủ, tách nhiều video cho nhiều đối</b>
      <i data-th="opt.games.d">Mỗi game một video, mỗi cái một timeline riêng, tên
         <code>[ngày] Opponent (game 1).mp4</code>. Tách theo game chứ không
         theo tên đối thủ.</i>
    </span></label>
    <label class="opt"><input type="radio" name="mode" value="full"><span>
      <b data-t="opt.full.t">Lược bỏ thời gian chờ turn đối thủ, gộp 1 video</b>
      <i data-th="opt.full.d">Một video hoàn chỉnh, kèm 1 file timeline .txt để dán vào mô tả
         YouTube. Đây là cái để đăng.</i>
    </span></label>
    <label class="opt"><input type="radio" name="mode" value="download"><span>
      <b data-t="opt.download.t">Chỉ tải video về, không cắt</b>
      <i data-th="opt.download.d">Lưu nguyên bản vào <code class="p-in">input\</code> rồi dừng. Để tải
         sẵn lúc mạng khoẻ, cắt sau — hoặc để giữ lại bản gốc.</i>
    </span></label>
    <details class="dev">
    <summary data-t="dev.summary">Tuỳ chọn cho lập trình viên</summary>
    <label class="opt"><input type="radio" name="mode" value="parts"><span>
      <b data-t="opt.parts.t">Cắt thành nhiều đoạn rời</b>
      <i data-th="opt.parts.d">Mỗi đoạn giữ lại thành một file riêng, không ghép. Để mở từng đoạn
         xem máy cắt có đúng chỗ không.</i>
    </span></label>
    <label class="opt"><input type="radio" name="mode" value="segments"><span>
      <b data-t="opt.segments.t">Chỉ phân tích, không tạo video</b>
      <i data-th="opt.segments.d">Chỉ ra danh sách khoảng sẽ giữ / sẽ bỏ và danh sách chương.
         Nhanh nhất.</i>
    </span></label>
    </details>
    <dl class="paths">
      <dt data-t="paths.video">Video ra</dt><dd><span class="p-out">output\</span><button
        class="small" data-open="output" data-t="btn.open" data-tt="tip.openFolder"
        title="Mở thư mục này trong Explorer">Mở</button></dd>
      <dt data-t="paths.parts">Đoạn rời ra</dt><dd><span class="p-parts">work\…\parts\</span><button
        class="small" data-open="work" data-t="btn.open" data-tt="tip.openWork"
        title="Mở thư mục work trong Explorer">Mở</button></dd>
    </dl>
  </div>

  <h2 data-t="h2.step2">2 &middot; Chọn nguồn</h2>
  <div class="card">
    <div class="row">
      <input type="text" id="url" data-tp="ph.url" placeholder="Dán link YouTube: https://www.youtube.com/watch?v=..." autocomplete="off">
      <button class="small" id="chopen" data-t="btn.chopen" data-tt="tip.chopen"
        title="Mở danh sách stream của kênh để lấy link">Chọn từ kênh&hellip;</button>
      <button class="go" id="start" data-t="btn.start">Tải &amp; chạy</button>
    </div>
    <div class="note" id="startmsg"></div>
    <div class="sep"><span data-t="sep.orRun">hoặc chạy một file đã có trong</span>
      <code class="p-in">input\</code>
      <button class="small" data-open="input" data-t="btn.open"
        data-tt="tip.openInput" title="Mở thư mục input trong Explorer">Mở</button></div>
    <div class="files" id="inputs"><div class="empty" data-t="empty.reading">đang đọc…</div></div>
  </div>


  <h2 data-t="h2.jobs">Công việc</h2>
  <div id="jobs"><div class="card empty" data-t="empty.jobs">Chưa có việc nào. Dán link ở trên để bắt đầu.</div></div>

  </div><!-- /tab-fn -->

  <div id="tab-trim" hidden>
  <h2 data-t="h2.trim">Cắt một đoạn ra file riêng</h2>
  <div class="card">
    <div class="note" data-th="trim.intro">Chọn video đang có trong
      <code class="p-in">input\</code>, tua tới chỗ cần rồi bấm
      <b>Đặt tại đây</b>. Đoạn cắt ra nằm cùng thư mục đó, chạy được ngay ở tab
      <b>Chức năng</b> &mdash; để thử thuật toán trên 15 phút thay vì 4 tiếng.</div>
    <div class="row">
      <select id="tsrc"></select>
      <button class="small" id="tload" data-t="btn.preview"
        data-tt="tip.preview" title="Nạp video này vào khung xem">Xem</button>
    </div>
    <video id="tvid" class="prev" controls preload="metadata"></video>
    <div class="marks">
      <label for="tstart" data-t="lbl.start">Điểm đầu</label>
      <input type="text" id="tstart" value="0:00" autocomplete="off">
      <button class="small" data-set="start" data-t="btn.setHere">Đặt tại đây</button>
      <button class="small" data-goto="start" data-t="btn.goto">Tới</button>
      <span class="gap"></span>
      <label for="tend" data-t="lbl.end">Điểm cuối</label>
      <input type="text" id="tend" value="" autocomplete="off">
      <button class="small" data-set="end" data-t="btn.setHere">Đặt tại đây</button>
      <button class="small" data-goto="end" data-t="btn.goto">Tới</button>
    </div>
    <div class="marks act">
      <button class="go" id="tcut" data-t="btn.cut">Cắt đoạn này ra</button>
      <span class="n" id="tinfo"></span>
    </div>
    <div class="note" id="tmsg"></div>
    <div class="note" data-t="trim.note">Cắt bằng cách copy nguyên luồng, không encode lại: 90 phút
      xong trong vài giây và hình y hệt bản gốc. Đổi lại điểm đầu bám vào
      keyframe gần nhất phía trước, nên đoạn ra có thể dài hơn yêu cầu vài
      giây &mdash; với việc cắt nhỏ để chạy thử thì không ảnh hưởng gì.</div>
  </div>
  </div><!-- /tab-trim -->

  <div id="tab-author" hidden>
  <h2 data-t="h2.author">Tác giả</h2>
  <div class="card">
    <dl class="kv">
      <dt data-t="author.dev">Dev</dt><dd>Nguyễn Thanh Hải</dd>
      <dt data-t="author.email">Email</dt><dd><a class="mail"
        href="mailto:nguyenthanhhaid13cn7@gmail.com"
        >nguyenthanhhaid13cn7@gmail.com</a>
        <button class="small" data-copy-text="nguyenthanhhaid13cn7@gmail.com"
          data-t="btn.copy" data-tt="tip.copyEmail"
          title="Copy email vào clipboard">Copy</button></dd>
    </dl>
  </div>
  </div><!-- /tab-author -->

  <div class="modal" id="chmodal" hidden>
    <div class="sheet">
      <div class="head">
        <b>Stream của kênh</b>
        <select id="chchan"></select>
        <select id="chlimit">
          <option value="10">10 mới nhất</option>
          <option value="20">20 mới nhất</option>
          <option value="100">100 mới nhất</option>
        </select>
        <button class="small" id="chload">Tải lại</button>
        <span class="n" id="chnote"></span>
        <button class="small" id="chclose">Đóng</button>
      </div>
      <div id="chlist"></div>
    </div>
  </div>

  <div class="foot" data-t="foot">
    Việc chỉ chạy khi cửa sổ đen (server) còn mở — đóng nó là mọi việc đang chạy
    bị dừng theo, kể cả ffmpeg. File tải dở vẫn resume được ở lượt sau. Trang
    này không thấy được việc chạy từ Start.cmd.
  </div>
</div>

<script>
const GIB = 1073741824;
function gib(n) { return (n / GIB).toFixed(2) + " GiB"; }
// GiB once it is worth it, MiB below: "0.06 GiB" reads as nothing.
function size(n) {
  if (!n) return "0";
  return n >= GIB ? (n / GIB).toFixed(2) + " GiB"
                  : (n / (1024 * 1024)).toFixed(0) + " MiB";
}
function esc(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }
function secs(n) { n = Math.round(n); const m = Math.floor(n / 60);
  return m ? m + "p " + (n % 60) + "s" : n + "s"; }
function pad(n) { return String(n).padStart(2, "0"); }
function stamp(t, timeOnly) {
  if (!t) return "";
  const d = new Date(t * 1000);
  const clock = pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  if (timeOnly) return clock;
  return pad(d.getDate()) + "/" + pad(d.getMonth() + 1) + "/" + d.getFullYear() +
         "  " + clock;
}
// "bắt đầu <khi nào> · xong <khi nào> · <bao lâu>", với ngày chỉ nhắc lại khi
// việc chạy vắt qua nửa đêm.
function whenLine(j, now) {
  if (!j.started) return "";
  const sameDay = j.finished &&
    new Date(j.started * 1000).toDateString() === new Date(j.finished * 1000).toDateString();
  const parts = ["Bắt đầu <b>" + stamp(j.started) + "</b>"];
  if (j.finished) parts.push("xong <b>" + stamp(j.finished, sameDay) + "</b>");
  parts.push((j.finished ? "mất " : "đã chạy ") +
             "<b>" + secs((j.finished || now) - j.started) + "</b>");
  return parts.join("   ·   ");
}

const STAGES = {
  queued:      ["Đang xếp hàng", ""],
  downloading: ["Đang tải", "run"],
  analysing:   ["Đang phân tích", "run"],
  rendering:   ["Đang cắt & render", "run"],
  done:        ["Xong", "done"],
  failed:      ["Lỗi", "bad"],
  cancelled:   ["Đã dừng", "bad"],
  interrupted: ["Bị ngắt", "bad"],
};
const ACTIVE = ["queued", "downloading", "analysing", "rendering"];
// ------------------------------------------------------------------ i18n ---
// Both languages arrive with the page: 124 short strings, which is smaller
// than one thumbnail and saves a request and a loading state.
const STRINGS = /*__I18N__*/{};
const FALLBACK = /*__LANG__*/"vi";

function readLang() {
  let want = null;
  try { want = localStorage.getItem("lang"); } catch (e) { want = null; }
  return STRINGS[want] ? want : FALLBACK;
}
let LANG = readLang();

// A key with no translation falls back to the default language rather than
// showing blank: a missing string should look wrong, not look empty.
function T(key) {
  const table = STRINGS[LANG] || {};
  if (key in table) return table[key];
  const base = STRINGS[FALLBACK] || {};
  return key in base ? base[key] : key;
}

// data-t sets text, data-th sets markup (for the few strings carrying <code>
// or <b>), data-tt a tooltip, data-tp a placeholder.
function applyLang() {
  document.documentElement.lang = LANG;
  for (const el of document.querySelectorAll("[data-t]"))
    el.textContent = T(el.dataset.t);
  for (const el of document.querySelectorAll("[data-th]"))
    el.innerHTML = T(el.dataset.th);
  for (const el of document.querySelectorAll("[data-tt]"))
    el.title = T(el.dataset.tt);
  for (const el of document.querySelectorAll("[data-tp]"))
    el.placeholder = T(el.dataset.tp);
  for (const b of document.querySelectorAll(".langs button"))
    b.classList.toggle("on", b.dataset.lang === LANG);
  document.getElementById("start").textContent =
    mode() === "download" ? T("btn.startDl") : T("btn.start");
  // data-th rebuilt the <code class="p-in"> spans, so the paths in them are
  // back to their placeholder text until the next poll. Ask for one now.
  if (LAST) refresh();
}

for (const b of document.querySelectorAll(".langs button")) {
  b.onclick = () => {
    LANG = b.dataset.lang;
    try { localStorage.setItem("lang", LANG); } catch (e) { /* private mode */ }
    applyLang();
  };
}

const MODES = { full: "gộp 1 video", games: "tách theo game",
                download: "chỉ tải về", parts: "nhiều đoạn rời",
                segments: "chỉ phân tích" };

// The mode is chosen once, at the top, and both sources use it.
function mode() {
  const el = document.querySelector('input[name=mode]:checked');
  return el ? el.value : "full";
}

// The mode changes what both buttons mean. Say so on the click rather than
// on the next poll a second later.
for (const el of document.querySelectorAll("input[name=mode]")) {
  el.addEventListener("change", () => {
    document.getElementById("start").textContent =
      mode() === "download" ? "Tải về" : "Tải & chạy";
    refresh();
  });
}

// ------------------------------------------------------------------ tabs ---
for (const b of document.querySelectorAll(".tabs button")) {
  b.onclick = () => {
    for (const other of document.querySelectorAll(".tabs button"))
      other.classList.toggle("on", other === b);
    for (const other of document.querySelectorAll(".tabs button"))
      document.getElementById("tab-" + other.dataset.tab).hidden =
        other !== b;
    if (b.dataset.tab === "trim") trimSources(LAST);
  };
}

let openLogs = new Set();
let LAST = null;                 // the last state, so a copy can carry context

// localhost counts as a secure context, so the clipboard API is available;
// the textarea is there for a browser that still refuses.
function hms(n) {
  if (!n) return "";
  n = Math.round(n);
  const h = Math.floor(n / 3600), m = Math.floor((n % 3600) / 60);
  return h ? h + ":" + pad(m) + ":" + pad(n % 60) : m + ":" + pad(n % 60);
}
function thousands(n) {
  return n == null ? "" : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch (e) {}
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch (e) { return false; }
}

// What a job looks like as pasteable text: the record first, then the log,
// so one paste says what was run as well as what it printed.
const COPY_FIELDS = [["title", "Tên"], ["mode", "Chế độ"], ["stage", "Bước"],
  ["percent", "%"], ["detail", "Chi tiết"], ["url", "URL"], ["file", "File"],
  ["size", "Dung lượng tải"], ["streams", "Luồng"], ["downloader", "Downloader"],
  ["length", "Thời lượng"], ["segments", "Segment"], ["kept", "Giữ"],
  ["chapters", "Chương"], ["output", "Video ra"], ["output_size", "Cỡ output"],
  ["chapters_path", "Timeline (.txt)"],
  ["warning", "Cảnh báo"], ["error", "Lỗi"]];

function jobAsText(job, log) {
  const NL = String.fromCharCode(10);
  const out = ["tieu_linh_hota job " + job.id];
  if (job.started) out.push("Bắt đầu: " + stamp(job.started));
  if (job.finished) out.push("Kết thúc: " + stamp(job.finished),
                             "Mất: " + secs(job.finished - job.started));
  for (const [key, label] of COPY_FIELDS)
    if (job[key] !== undefined && job[key] !== null && job[key] !== "")
      out.push(label + ": " + job[key]);
  out.push("", "---- log (" + (log || []).length + " dòng) ----", "");
  return out.concat(log || []).join(NL);
}

// Two buttons, nothing to type. Every destructive action goes through here.
function ask(...lines) {
  return confirm(lines.join(String.fromCharCode(10)));
}

async function post(path, body) {
  const r = await fetch(path, { method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}) });
  return { ok: r.ok, data: await r.json().catch(() => ({})) };
}

function note(text, bad) {
  const el = document.getElementById("startmsg");
  el.className = bad ? "note bad" : "note";
  el.textContent = text;
}

async function startJob(payload) {
  const btn = document.getElementById("start");
  btn.disabled = true;
  const msg = document.getElementById("startmsg");
  msg.className = "note"; msg.textContent = "";
  const { ok, data } = await post("/api/jobs", payload);
  btn.disabled = false;
  if (!ok) { msg.className = "note bad"; msg.textContent = data.error || "không bắt đầu được"; }
  else { document.getElementById("url").value = ""; refresh(); }
}

document.getElementById("start").onclick = () => startJob({
  url: document.getElementById("url").value, mode: mode() });
document.getElementById("url").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("start").click(); });

function jobCard(j, now) {
  const [label, cls] = STAGES[j.stage] || [j.stage, ""];
  const active = ACTIVE.includes(j.stage);
  const idle = now - (j.updated || 0);
  let html = '<div class="card job">';
  html += '<div class="head"><span class="t">' + esc(j.title || j.file || j.url) + '</span>';
  html += '<span class="badge ' + cls + '">' + label + (active ? " " + (j.percent || 0) + "%" : "") + '</span>';
  if (active) html += '<button class="small" data-cancel="' + j.id + '">Dừng</button>';
  else html += '<button class="small danger" data-jobdel="' + j.id + '" ' +
               'title="Xoá việc này khỏi danh sách. Không xoá video.">Xoá</button>';
  html += '<button class="small" data-log="' + j.id + '">Chi tiết</button>';
  html += '<button class="small" data-copy="' + j.id + '" ' +
          'title="Copy toàn bộ log + thông tin việc này vào clipboard">Copy log</button>';
  // Where the result of this job landed: output\ for a finished video,
  // work\ for the loose pieces.
  const home = j.mode === "download" ? "input"
             : j.output ? "output"
             : (j.mode === "parts" ? "work" : "");
  if (home && !active)
    html += '<button class="small" data-openjob="' + j.id + '" ' +
            'data-where="' + home + '" title="Mở thư mục chứa kết quả">Mở thư mục</button>';
  html += '</div>';
  const when = whenLine(j, now);
  if (when) html += '<div class="when">' + when + '</div>';
  if (active) html += '<div class="prog"><i style="width:' + (j.percent || 0) + '%"></i></div>';
  if (j.detail) html += '<div class="meta">' + esc(j.detail) + '</div>';

  // A bar that stops moving and an app that has hung look identical, so say
  // how long it has been quiet rather than leaving it to be guessed -- but
  // scale the threshold by how often this job reports, or a render that
  // prints once per piece is called stuck between every two pieces.
  const quiet = Math.max(20, (j.gap || 0) * 2.5);
  if (active && idle > quiet)
    html += '<div class="note warn">Không có dữ liệu mới trong ' + secs(idle) + '.</div>';
  if (j.warning) html += '<div class="note warn">' + esc(j.warning) + '</div>';
  if (j.error) html += '<div class="note bad">' + esc(j.error) + '</div>';

  const kv = [];
  if (j.mode && j.mode !== "full") kv.push(["Chế độ", MODES[j.mode] || j.mode]);
  if (j.size) kv.push(["Dung lượng tải", j.size]);
  if (j.streams) kv.push(["Luồng", j.streams]);
  if (j.downloader) kv.push(["Downloader", j.downloader]);
  if (j.length) kv.push(["Thời lượng", j.length]);
  if (j.segments != null) kv.push(["Segment", j.segments + (j.kept ? " · giữ " + j.kept : "")]);
  if (j.chapters != null) kv.push(["Chương", String(j.chapters)]);
  if (j.file) kv.push(["File nguồn", j.file]);
  if (j.output) kv.push([j.mode === "download" ? "File đã tải" : "Video ra",
                         j.output + (j.output_size ? "  (" + j.output_size + ")" : "")]);
  if (j.chapters_path) kv.push(["Timeline (.txt)", j.chapters_path]);

  if (kv.length) {
    html += '<dl class="kv">';
    for (const [k, v] of kv) html += "<dt>" + esc(k) + "</dt><dd>" + esc(v) + "</dd>";
    html += "</dl>";
  }
  if (openLogs.has(j.id)) html += '<pre id="log-' + j.id + '">đang tải log…</pre>';
  html += "</div>";
  return html;
}

async function loadLog(id) {
  const el = document.getElementById("log-" + id);
  if (!el) return;
  const r = await fetch("/api/jobs/" + id + "/log");
  const d = await r.json().catch(() => ({ log: [] }));
  el.textContent = (d.log || []).slice(-200).join("\n") || "(chưa có gì)";
  el.scrollTop = el.scrollHeight;
}

async function refresh() {
  let s;
  try { s = await (await fetch("/api/state")).json(); }
  catch (e) { return; }
  LAST = s;

  // The folders are only known at run time, and a person looking for a file
  // in Explorer needs the whole path, not "output\".
  const P = s.paths || {};
  const put = (sel, value) => document.querySelectorAll(sel)
    .forEach(el => { if (value) el.textContent = value; });
  put(".p-out", P.output ? P.output + "\\" : "");
  put(".p-in", P.input ? P.input + "\\" : "");
  put(".p-parts", P.parts || "");

  const F = s.folders || {};
  for (const [id, key] of [["szin", "input"], ["szout", "output"]]) {
    const f = F[key] || {};
    document.getElementById(id).textContent =
      size(f.bytes) + "   " + (f.files || 0) + " file";
  }

  const d = s.drive, pct = d.total ? Math.round(100 * d.used / d.total) : 0;
  document.getElementById("dv").textContent = "Ổ " + d.root;
  document.getElementById("dvbar").style.width = pct + "%";
  document.getElementById("dvfree").textContent =
    "còn " + gib(d.free) + " / " + gib(d.total);

  const inputs = document.getElementById("inputs");
  if (!s.inputs.length) {
    inputs.innerHTML = '<div class="empty">Chưa có video nào ở đây.</div>';
  } else {
    const noRun = mode() === "download";
    inputs.innerHTML = s.inputs.map(f =>
      '<div class="file"><span class="nm">' + esc(f.name) + '</span>' +
      '<span class="sz">' + size(f.bytes) + "</span>" +
      '<button class="small" data-run="' + esc(f.name) + '"' +
        (noRun ? ' disabled title="Đang chọn chế độ chỉ tải về, ' +
                 'file này thì đã tải rồi"' : '') + '>Chạy</button>' +
      '<button class="small" data-show="' + esc(f.name) + '" ' +
        'title="Mở thư mục chứa file này, chọn sẵn nó">Mở</button>' +
      '<button class="small danger" data-del="' + esc(f.name) + '" data-size="' +
        gib(f.bytes) + '" title="Chuyển vào Thùng rác, có thể phục hồi">Xoá</button>' +
      "</div>").join("");
  }

  if (!document.getElementById("tab-trim").hidden) trimSources(s);

  const jobs = document.getElementById("jobs");
  jobs.innerHTML = s.jobs.length
    ? s.jobs.map(j => jobCard(j, s.now)).join("")
    : '<div class="card empty">Chưa có việc nào. Dán link ở trên để bắt đầu.</div>';
  for (const id of openLogs) loadLog(id);
}

document.addEventListener("click", async e => {
  const run = e.target.closest("[data-run]");
  if (run) return startJob({ file: run.dataset.run, mode: mode() });
  const oj = e.target.closest("[data-openjob]");
  if (oj) {
    const job = ((LAST && LAST.jobs) || []).find(j => j.id === oj.dataset.openjob) || {};
    const SEP = String.fromCharCode(92);
    const leaf = job.output ? job.output.split(SEP).pop() : null;
    return void post("/api/reveal", { where: oj.dataset.where, file: leaf });
  }
  const open = e.target.closest("[data-open]");
  if (open) return void post("/api/reveal", { where: open.dataset.open });
  const show = e.target.closest("[data-show]");
  if (show) return void post("/api/reveal", { where: "input", file: show.dataset.show });
  const ct = e.target.closest("[data-copy-text]");
  if (ct) {
    const was = ct.textContent;
    ct.textContent = (await copyText(ct.dataset.copyText)) ? "Đã copy"
                                                           : "Không copy được";
    setTimeout(() => { ct.textContent = was; }, 1500);
    return;
  }
  const cp = e.target.closest("[data-copy]");
  if (cp) {
    const id = cp.dataset.copy;
    const was = cp.textContent;
    cp.textContent = "...";
    let log = [];
    try {
      const r = await fetch("/api/jobs/" + id + "/log");
      log = (await r.json()).log || [];
    } catch (e) {}
    const job = ((LAST && LAST.jobs) || []).find(j => j.id === id) || { id: id };
    const ok = await copyText(jobAsText(job, log));
    cp.textContent = ok ? "Đã copy" : "Không copy được";
    setTimeout(() => { cp.textContent = was; }, 1800);
    return;
  }
  const clr = e.target.closest("[data-clear]");
  if (clr) {
    const key = clr.dataset.clear;
    const f = ((LAST && LAST.folders) || {})[key] || {};
    const where = ((LAST && LAST.paths) || {})[key] || key;
    if (!f.files) { note("Thư mục này đang trống."); return; }
    if (!ask("Dọn sạch thư mục này?", "", where, "",
             f.files + " file, " + size(f.bytes), "",
             "Tất cả sẽ được chuyển vào Thùng rác, có thể phục hồi.")) return;
    const { ok, data } = await post("/api/folders/clear", { where: key });
    note(ok ? (data.message || "đã dọn") : (data.error || "không dọn được"), !ok);
    return refresh();
  }
  const del = e.target.closest("[data-del]");
  if (del) {
    const name = del.dataset.del;
    if (!ask("Xoá file này?", "", name, "(" + del.dataset.size + ")", "",
             "File sẽ được chuyển vào Thùng rác, có thể phục hồi.")) return;
    const { ok, data } = await post("/api/files/delete", { file: name });
    note(ok ? "Đã chuyển vào Thùng rác: " + name
            : (data.error || "không xoá được"), !ok);
    return refresh();
  }
  const jd = e.target.closest("[data-jobdel]");
  if (jd) {
    const id = jd.dataset.jobdel;
    const job = ((LAST && LAST.jobs) || []).find(j => j.id === id) || {};
    if (!ask("Xoá việc này khỏi danh sách?", "", job.title || id, "",
             "Chỉ xoá bản ghi và log của việc.",
             "Video đã tải và video đã cắt KHÔNG bị xoá.")) return;
    const { ok, data } = await post("/api/jobs/" + id + "/delete", {});
    const msg = document.getElementById("startmsg");
    msg.className = ok ? "note" : "note bad";
    msg.textContent = ok ? "Đã xoá việc khỏi danh sách."
                         : (data.error || "không xoá được");
    return refresh();
  }
  const cancel = e.target.closest("[data-cancel]");
  if (cancel) { await post("/api/jobs/" + cancel.dataset.cancel + "/cancel"); return refresh(); }
  const log = e.target.closest("[data-log]");
  if (log) {
    const id = log.dataset.log;
    openLogs.has(id) ? openLogs.delete(id) : openLogs.add(id);
    return refresh();
  }
});

// ------------------------------------------------------------------ trim ---
// A preview and two marks. The point is not to type a timestamp -- the command
// line is better at that -- but to see the frame and take the time off it.
const tvid = document.getElementById("tvid");

// "1:02:03", "2:03", "90" and "1h02m03" all mean what they look like.
function secs(text) {
  const t = String(text == null ? "" : text).trim()
              .replace(/[hm]/g, ":").replace(/:+$/, "");
  if (!t) return NaN;
  const parts = t.split(":");
  let v = 0;
  for (const part of parts) {
    const n = Number(part);
    if (part === "" || !isFinite(n) || n < 0) return NaN;
    v = v * 60 + n;
  }
  return v;
}

function clock(v) {
  v = Math.max(0, Math.round(v || 0));
  return Math.floor(v / 3600) + ":" + pad(Math.floor((v % 3600) / 60))
         + ":" + pad(v % 60);
}

function tnote(text, bad) {
  const el = document.getElementById("tmsg");
  el.className = bad ? "note bad" : "note";
  el.textContent = text;
}

// Rebuilt only when the file list actually changes, so the poll every second
// does not throw away what the reader picked.
function trimSources(s) {
  const sel = document.getElementById("tsrc");
  const names = ((s && s.inputs) || []).map(f => f.name);
  const sig = names.join("|");
  if (sel.dataset.sig === sig) return;
  sel.dataset.sig = sig;
  const had = sel.value;
  sel.innerHTML = names.length
    ? names.map(n => '<option value="' + esc(n) + '">' + esc(n) + "</option>").join("")
    : '<option value="">chưa có video nào trong thư mục input</option>';
  if (names.indexOf(had) >= 0) sel.value = had;
}

function tload() {
  const name = document.getElementById("tsrc").value;
  if (!name) return tnote("Chưa có video nào để xem.", true);
  tvid.src = "/media?name=" + encodeURIComponent(name);
  tvid.load();
  tnote("");
}

document.getElementById("tload").onclick = tload;
document.getElementById("tsrc").onchange = tload;

tvid.addEventListener("loadedmetadata", () => {
  document.getElementById("tend").value = clock(tvid.duration);
  document.getElementById("tstart").value = "0:00:00";
  tinfo();
});
tvid.addEventListener("error", () => tnote(
  "Trình duyệt không phát được file này. mp4 và webm thì được; mkv, ts, avi "
  + "thì thường không, nhưng vẫn cắt được nếu tự nhập mốc.", true));

function tinfo() {
  const a = secs(document.getElementById("tstart").value);
  const b = secs(document.getElementById("tend").value);
  const el = document.getElementById("tinfo");
  if (!isFinite(a) || !isFinite(b)) { el.textContent = "mốc không đọc được"; return; }
  el.textContent = b > a
    ? "dài " + clock(b - a) + "   (" + clock(a) + " → " + clock(b) + ")"
    : "điểm cuối phải sau điểm đầu";
}
for (const id of ["tstart", "tend"])
  document.getElementById(id).addEventListener("input", tinfo);

document.addEventListener("click", e => {
  const set = e.target.closest("[data-set]");
  if (set) {
    document.getElementById("t" + set.dataset.set).value = clock(tvid.currentTime);
    return tinfo();
  }
  const go = e.target.closest("[data-goto]");
  if (go) {
    const v = secs(document.getElementById("t" + go.dataset.goto).value);
    if (isFinite(v)) tvid.currentTime = v;
  }
});

document.getElementById("tcut").onclick = async () => {
  const name = document.getElementById("tsrc").value;
  const a = secs(document.getElementById("tstart").value);
  const b = secs(document.getElementById("tend").value);
  if (!name) return tnote("Chưa chọn video.", true);
  if (!isFinite(a) || !isFinite(b) || b <= a)
    return tnote("Mốc thời gian không hợp lệ.", true);
  if (!ask("Cắt đoạn này ra thành file mới?", "", name, "",
           clock(a) + " → " + clock(b) + "   (dài " + clock(b - a) + ")", "",
           "File mới nằm trong thư mục input, không sửa gì vào bản gốc."))
    return;
  const btn = document.getElementById("tcut");
  btn.disabled = true;
  tnote("đang cắt…");
  const { ok, data } = await post("/api/trim", { name: name, start: a, end: b });
  btn.disabled = false;
  if (!ok) return tnote(data.error || "không cắt được", true);
  tnote("Đã cắt: " + data.name + "   " + size(data.bytes)
        + "   dài thật " + clock(data.length)
        + (data.length - (b - a) > 1.5 ? "  (dài hơn yêu cầu do bám keyframe)" : ""));
  refresh();
};

// ---------------------------------------------------------------- channel ---
// A picker, deliberately separate from the rest of the page: it hands back a
// link and changes nothing else. The listing is flat -- no player request per
// video -- which is why a hundred rows take about a second, and also why it
// carries no date. A date is one request per video, so it is fetched only for
// a row somebody asks about.
const chModal = document.getElementById("chmodal");
const chList = document.getElementById("chlist");
const chNote = document.getElementById("chnote");
const chChan = document.getElementById("chchan");

function chShow(open) { chModal.hidden = !open; }

// The channel list comes from the server so there is one list, not two.
// Filled on the first open, then left alone: it does not change while the
// page is up, and refilling it would throw away the reader's choice.
async function chChannels() {
  if (chChan.options.length) return;
  const { ok, data } = await post("/api/channels", {});
  const rows = (ok && data.channels) || [];
  chChan.innerHTML = rows.map(c =>
    '<option value="' + esc(c.url) + '">' + esc(c.name) + "</option>").join("");
}

document.getElementById("chopen").onclick = async () => {
  chShow(true);
  await chChannels();
  chLoad();
};
document.getElementById("chclose").onclick = () => chShow(false);
document.getElementById("chload").onclick = () => chLoad();
document.getElementById("chlimit").onchange = () => chLoad();
chChan.onchange = () => chLoad();
chModal.addEventListener("click", e => { if (e.target === chModal) chShow(false); });
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !chModal.hidden) chShow(false);
});

async function chLoad() {
  const limit = document.getElementById("chlimit").value;
  chNote.textContent = "đang lấy danh sách…";
  chList.innerHTML = "";
  const { ok, data } = await post("/api/channel",
                                  { limit: Number(limit), url: chChan.value });
  if (!ok) { chNote.textContent = data.error || "không lấy được"; return; }
  const rows = data.entries || [];
  chNote.textContent = rows.length + " video";
  chList.innerHTML = rows.map(v => {
    const live = v.live === "is_live" || v.live === "is_upcoming";
    const meta = [live ? "ĐANG PHÁT" : hms(v.duration),
                  v.views != null ? thousands(v.views) + " view" : ""]
                 .filter(Boolean).join("   \u00b7   ");
    return '<div class="vid' + (live ? " live" : "") + '">' +
      '<img loading="lazy" src="' + esc(v.thumb) + '" alt="">' +
      '<div class="body"><div class="t">' + esc(v.title) + "</div>" +
      '<div class="m">' + esc(meta) + '<span id="d-' + esc(v.id) + '"></span></div>' +
      '<div class="acts">' +
      (live ? '<span class="m">chưa kết thúc, không tải được</span>'
            : '<button class="small" data-use="' + esc(v.url) + '">Dùng link này</button>' +
              '<button class="small" data-cl="' + esc(v.url) + '">Copy link</button>' +
              '<button class="small" data-vd="' + esc(v.id) + '">Ngày phát</button>') +
      "</div></div></div>";
  }).join("") || '<div class="vid"><span class="m">Kênh này chưa có stream nào.</span></div>';
}

document.addEventListener("click", async e => {
  const use = e.target.closest("[data-use]");
  if (use) {
    document.getElementById("url").value = use.dataset.use;
    chShow(false);
    document.getElementById("url").focus();
    return;
  }
  const cl = e.target.closest("[data-cl]");
  if (cl) {
    const was = cl.textContent;
    cl.textContent = (await copyText(cl.dataset.cl)) ? "Đã copy" : "Không copy được";
    setTimeout(() => { cl.textContent = was; }, 1500);
    return;
  }
  const vd = e.target.closest("[data-vd]");
  if (vd) {
    const id = vd.dataset.vd;
    vd.textContent = "...";
    const { ok, data } = await post("/api/video-date", { id: id });
    const slot = document.getElementById("d-" + id);
    if (ok && data.when) {
      if (slot) slot.textContent = "   \u00b7   phát " + stamp(data.when);
      vd.remove();
    } else {
      vd.textContent = "không lấy được";
    }
  }
});

applyLang();
refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""

# One build step, not a format(): the page is full of CSS braces and JS
# template syntax, and a replace of two markers cannot misread any of it.
# The markers carry a dummy value after them, so the template is valid
# JavaScript on its own and node --check can read it before the build; the
# replacement swallows the dummy along with the marker.
PAGE = (_HTML
        .replace("/*__I18N__*/{}",
                 json.dumps(i18n.STRINGS, ensure_ascii=False))
        .replace('/*__LANG__*/"vi"', json.dumps(i18n.DEFAULT)))
assert "__I18N__" not in PAGE and "__LANG__" not in PAGE
