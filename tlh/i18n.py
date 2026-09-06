"""Every word the page shows, in both languages it speaks.

Vietnamese is the default and the original: this is a tool for one Vietnamese
streamer's VODs, and the person using it reads Vietnamese. English is here so
the page can be shown to someone who does not.

The page keeps its Vietnamese inline in the HTML as well as here, so it reads
correctly before the script runs and even if the script never runs. That is a
duplication on purpose; `check()` guards the failure that actually happens,
which is a key translated in one language and not the other.

Not in here: anything the SERVER writes. Job details, progress lines and API
errors are produced by tlh/web.py and run.py and arrive already worded, so in
English mode those lines stay Vietnamese. Translating them means carrying a
language through the API, which is a bigger change than the page needed.
"""

VI = {
    # ---- chrome
    "head.title": "Cắt VOD stream từ kênh",
    "tab.fn": "Chức năng",
    "tab.trim": "Hỗ trợ cắt ghép",
    "tab.author": "Tác giả",
    "lang.tip": "Đổi ngôn ngữ giao diện",

    # ---- shared buttons and tips
    "btn.open": "Mở",
    "btn.clear": "Dọn",
    "btn.copy": "Copy",
    "tip.openFolder": "Mở thư mục này trong Explorer",
    "tip.clearFolder": "Chuyển mọi file trong thư mục này vào Thùng rác",
    "tip.openWork": "Mở thư mục work trong Explorer",
    "tip.openInput": "Mở thư mục input trong Explorer",

    # ---- 1. what to do
    "h2.step1": "1 · Chọn việc muốn làm",
    "opt.games.t": "Lược bỏ thời gian chờ turn đối thủ, tách nhiều video cho nhiều đối",
    "opt.games.d": "Mỗi game một video, mỗi cái một timeline riêng, tên "
                   "<code>[ngày] Opponent (game 1).mp4</code>. Tách theo game "
                   "chứ không theo tên đối thủ.",
    "opt.full.t": "Lược bỏ thời gian chờ turn đối thủ, gộp 1 video",
    "opt.full.d": "Một video hoàn chỉnh, kèm 1 file timeline .txt để dán vào "
                  "mô tả YouTube. Đây là cái để đăng.",
    "opt.download.t": "Chỉ tải video về, không cắt",
    "opt.download.d": 'Lưu nguyên bản vào <code class="p-in">input\\</code> rồi '
                      "dừng. Để tải sẵn lúc mạng khoẻ, cắt sau — hoặc để giữ "
                      "lại bản gốc.",
    "dev.summary": "Tuỳ chọn cho lập trình viên",
    "opt.parts.t": "Cắt thành nhiều đoạn rời",
    "opt.parts.d": "Mỗi đoạn giữ lại thành một file riêng, không ghép. Để mở "
                   "từng đoạn xem máy cắt có đúng chỗ không.",
    "opt.segments.t": "Chỉ phân tích, không tạo video",
    "opt.segments.d": "Chỉ ra danh sách khoảng sẽ giữ / sẽ bỏ và danh sách "
                      "chương. Nhanh nhất.",
    "paths.video": "Video ra",
    "paths.parts": "Đoạn rời ra",

    # ---- 2. the source
    "h2.step2": "2 · Chọn nguồn",
    "ph.url": "Dán link YouTube: https://www.youtube.com/watch?v=...",
    "btn.chopen": "Chọn từ kênh…",
    "tip.chopen": "Mở danh sách stream của kênh để lấy link",
    "btn.start": "Tải & chạy",
    "btn.startDl": "Tải về",
    "sep.orRun": "hoặc chạy một file đã có trong",
    "empty.reading": "đang đọc…",
    "empty.noInput": "Chưa có video nào ở đây.",
    "btn.run": "Chạy",
    "btn.delete": "Xoá",
    "tip.showFile": "Mở thư mục chứa file này, chọn sẵn nó",
    "tip.deleteFile": "Chuyển vào Thùng rác, có thể phục hồi",
    "tip.noRunInDl": "Đang chọn chế độ chỉ tải về, file này thì đã tải rồi",

    # ---- jobs
    "h2.jobs": "Công việc",
    "empty.jobs": "Chưa có việc nào. Dán link ở trên để bắt đầu.",
    "job.stop": "Dừng",
    "job.remove": "Xoá",
    "job.detail": "Chi tiết",
    "job.copyLog": "Copy log",
    "job.openFolder": "Mở thư mục",
    "tip.copyLog": "Copy toàn bộ log + thông tin việc này vào clipboard",
    "tip.openResult": "Mở thư mục chứa kết quả",
    "kv.mode": "Chế độ",
    "kv.downloaded": "Dung lượng tải",
    "kv.streams": "Luồng",
    "kv.downloader": "Downloader",
    "kv.length": "Thời lượng",
    "kv.segments": "Segment",
    "kv.kept": "giữ",
    "kv.chapters": "Chương",
    "kv.source": "File nguồn",
    "kv.output": "Video ra",
    "kv.downloadedFile": "File đã tải",
    "kv.timeline": "Timeline (.txt)",
    "job.started": "Bắt đầu",
    "job.finished": "xong",
    "job.took": "mất",
    "job.stale": "Không có dữ liệu mới",

    # ---- trim tab
    "h2.trim": "Cắt một đoạn ra file riêng",
    "trim.intro": "Chọn video đang có trong "
                  '<code class="p-in">input\\</code>, tua tới chỗ cần rồi bấm '
                  "<b>Đặt tại đây</b>. Đoạn cắt ra nằm cùng thư mục đó, chạy "
                  "được ngay ở tab <b>Chức năng</b> — để thử thuật toán trên "
                  "15 phút thay vì 4 tiếng.",
    "btn.preview": "Xem",
    "tip.preview": "Nạp video này vào khung xem",
    "lbl.start": "Điểm đầu",
    "lbl.end": "Điểm cuối",
    "btn.setHere": "Đặt tại đây",
    "btn.goto": "Tới",
    "btn.cut": "Cắt đoạn này ra",
    "trim.note": "Cắt bằng cách copy nguyên luồng, không encode lại: 90 phút "
                 "xong trong vài giây và hình y hệt bản gốc. Đổi lại điểm đầu "
                 "bám vào keyframe gần nhất phía trước, nên đoạn ra có thể dài "
                 "hơn yêu cầu vài giây — với việc cắt nhỏ để chạy thử thì "
                 "không ảnh hưởng gì.",
    "trim.noVideo": "chưa có video nào trong thư mục input",
    "trim.pickFirst": "Chưa có video nào để xem.",
    "trim.noSource": "Chưa chọn video.",
    "trim.badMarks": "Mốc thời gian không hợp lệ.",
    "trim.unreadable": "mốc không đọc được",
    "trim.endAfterStart": "điểm cuối phải sau điểm đầu",
    "trim.long": "dài",
    "trim.cutting": "đang cắt…",
    "trim.cutFailed": "không cắt được",
    "trim.done": "Đã cắt:",
    "trim.realLength": "dài thật",
    "trim.keyframeNote": "(dài hơn yêu cầu do bám keyframe)",
    "trim.cantPlay": "Trình duyệt không phát được file này. mp4 và webm thì "
                     "được; mkv, ts, avi thì thường không, nhưng vẫn cắt được "
                     "nếu tự nhập mốc.",
    "ask.cutTitle": "Cắt đoạn này ra thành file mới?",
    "ask.cutNote": "File mới nằm trong thư mục input, không sửa gì vào bản gốc.",

    # ---- channel picker
    "ch.title": "Stream của kênh",
    "ch.newest": "mới nhất",
    "ch.reload": "Tải lại",
    "ch.close": "Đóng",
    "ch.loading": "đang lấy danh sách…",
    "ch.failed": "không lấy được",
    "ch.videos": "video",
    "ch.empty": "Kênh này chưa có stream nào.",
    "ch.live": "ĐANG PHÁT",
    "ch.liveNoDl": "chưa kết thúc, không tải được",
    "ch.use": "Dùng link này",
    "ch.copy": "Copy link",
    "ch.date": "Ngày phát",
    "ch.aired": "phát",
    "ch.views": "view",
    "copied": "Đã copy",
    "copyFailed": "Không copy được",

    # ---- confirmations and messages
    "ask.deleteFile": "Xoá file này?",
    "ask.recycle": "File sẽ được chuyển vào Thùng rác, có thể phục hồi.",
    "ask.clearFolder": "Dọn sạch thư mục này?",
    "ask.clearNote": "Tất cả sẽ được chuyển vào Thùng rác, có thể phục hồi.",
    "ask.emptyFolder": "Thư mục này đang trống.",
    "ask.stopJob": "Dừng việc này?",
    "ask.removeJob": "Xoá thẻ công việc này?",
    "msg.recycled": "Đã chuyển vào Thùng rác:",
    "msg.deleteFailed": "không xoá được",
    "msg.clearFailed": "không dọn được",
    "msg.cleared": "đã dọn",
    "file": "file",

    # ---- author
    "h2.author": "Tác giả",
    "author.dev": "Dev",
    "author.email": "Email",
    "tip.copyEmail": "Copy email vào clipboard",

    # ---- foot
    "foot": "Việc chỉ chạy khi cửa sổ đen (server) còn mở — đóng nó là mọi việc "
            "đang chạy bị dừng theo, kể cả ffmpeg. File tải dở vẫn resume được "
            "ở lượt sau. Trang này không thấy được việc chạy từ Start.cmd.",
}

EN = {
    "head.title": "Cut stream VODs from the channel",
    "tab.fn": "Main",
    "tab.trim": "Trim helper",
    "tab.author": "Author",
    "lang.tip": "Change the interface language",

    "btn.open": "Open",
    "btn.clear": "Empty",
    "btn.copy": "Copy",
    "tip.openFolder": "Open this folder in Explorer",
    "tip.clearFolder": "Send every file in this folder to the Recycle Bin",
    "tip.openWork": "Open the work folder in Explorer",
    "tip.openInput": "Open the input folder in Explorer",

    "h2.step1": "1 · Choose what to do",
    "opt.games.t": "Drop the waiting on the opponent's turn, one video per game",
    "opt.games.d": "One video per game, each with its own timeline, named "
                   "<code>[date] Opponent (game 1).mp4</code>. Split by game, "
                   "not by the opponent's name.",
    "opt.full.t": "Drop the waiting on the opponent's turn, one video in total",
    "opt.full.d": "One finished video, with a timeline .txt to paste into the "
                  "YouTube description. This is the one to upload.",
    "opt.download.t": "Only download the video, cut nothing",
    "opt.download.d": 'Save the original into <code class="p-in">input\\</code> '
                      "and stop. For downloading while the connection is good "
                      "and cutting later — or for keeping the original.",
    "dev.summary": "Developer options",
    "opt.parts.t": "Cut into loose pieces",
    "opt.parts.d": "Every kept stretch as its own file, not joined. For opening "
                   "them one by one to see whether the cuts landed right.",
    "opt.segments.t": "Analyse only, produce no video",
    "opt.segments.d": "Just the list of what would be kept and dropped, and the "
                      "chapter list. The quickest.",
    "paths.video": "Video out",
    "paths.parts": "Loose pieces",

    "h2.step2": "2 · Choose a source",
    "ph.url": "Paste a YouTube link: https://www.youtube.com/watch?v=...",
    "btn.chopen": "From the channel…",
    "tip.chopen": "Open the channel's stream list to take a link from it",
    "btn.start": "Download & run",
    "btn.startDl": "Download",
    "sep.orRun": "or run a file already in",
    "empty.reading": "reading…",
    "empty.noInput": "Nothing here yet.",
    "btn.run": "Run",
    "btn.delete": "Delete",
    "tip.showFile": "Open the folder holding this file, with it selected",
    "tip.deleteFile": "Move to the Recycle Bin, recoverable",
    "tip.noRunInDl": "Download-only is selected, and this file is already "
                     "downloaded",

    "h2.jobs": "Jobs",
    "empty.jobs": "Nothing running. Paste a link above to start.",
    "job.stop": "Stop",
    "job.remove": "Remove",
    "job.detail": "Details",
    "job.copyLog": "Copy log",
    "job.openFolder": "Open folder",
    "tip.copyLog": "Copy the whole log and this job's details to the clipboard",
    "tip.openResult": "Open the folder holding the result",
    "kv.mode": "Mode",
    "kv.downloaded": "Downloaded",
    "kv.streams": "Streams",
    "kv.downloader": "Downloader",
    "kv.length": "Length",
    "kv.segments": "Segments",
    "kv.kept": "kept",
    "kv.chapters": "Chapters",
    "kv.source": "Source file",
    "kv.output": "Video out",
    "kv.downloadedFile": "Downloaded file",
    "kv.timeline": "Timeline (.txt)",
    "job.started": "Started",
    "job.finished": "finished",
    "job.took": "took",
    "job.stale": "No new data",

    "h2.trim": "Cut a range out into its own file",
    "trim.intro": "Pick a video already in "
                  '<code class="p-in">input\\</code>, seek to the moment and '
                  "press <b>Set here</b>. The clip lands in the same folder and "
                  "can be run straight from the <b>Main</b> tab — to try the "
                  "detector on fifteen minutes instead of four hours.",
    "btn.preview": "Preview",
    "tip.preview": "Load this video into the player",
    "lbl.start": "Start",
    "lbl.end": "End",
    "btn.setHere": "Set here",
    "btn.goto": "Go",
    "btn.cut": "Cut this range out",
    "trim.note": "Cut by copying the streams, with no re-encode: ninety minutes "
                 "in a few seconds, and the original pixels. In exchange the "
                 "start lands on the nearest keyframe before it, so a clip can "
                 "run a few seconds longer than asked — which for cutting a "
                 "test piece down does not matter.",
    "trim.noVideo": "no video in the input folder yet",
    "trim.pickFirst": "There is no video to preview.",
    "trim.noSource": "No video chosen.",
    "trim.badMarks": "Those marks are not valid.",
    "trim.unreadable": "marks unreadable",
    "trim.endAfterStart": "the end must come after the start",
    "trim.long": "length",
    "trim.cutting": "cutting…",
    "trim.cutFailed": "could not cut",
    "trim.done": "Cut:",
    "trim.realLength": "real length",
    "trim.keyframeNote": "(longer than asked, snapped to a keyframe)",
    "trim.cantPlay": "The browser cannot play this file. mp4 and webm it can; "
                     "mkv, ts and avi usually not — but it can still be cut if "
                     "you type the marks in.",
    "ask.cutTitle": "Cut this range out into a new file?",
    "ask.cutNote": "The new file goes into the input folder; the original is "
                   "not touched.",

    "ch.title": "Streams on the channel",
    "ch.newest": "newest",
    "ch.reload": "Reload",
    "ch.close": "Close",
    "ch.loading": "fetching the list…",
    "ch.failed": "could not fetch",
    "ch.videos": "videos",
    "ch.empty": "This channel has no streams yet.",
    "ch.live": "LIVE NOW",
    "ch.liveNoDl": "still live, cannot be downloaded",
    "ch.use": "Use this link",
    "ch.copy": "Copy link",
    "ch.date": "Air date",
    "ch.aired": "aired",
    "ch.views": "views",
    "copied": "Copied",
    "copyFailed": "Could not copy",

    "ask.deleteFile": "Delete this file?",
    "ask.recycle": "It goes to the Recycle Bin and can be restored.",
    "ask.clearFolder": "Empty this folder?",
    "ask.clearNote": "Everything goes to the Recycle Bin and can be restored.",
    "ask.emptyFolder": "This folder is already empty.",
    "ask.stopJob": "Stop this job?",
    "ask.removeJob": "Remove this job card?",
    "msg.recycled": "Moved to the Recycle Bin:",
    "msg.deleteFailed": "could not delete",
    "msg.clearFailed": "could not empty",
    "msg.cleared": "emptied",
    "file": "files",

    "h2.author": "Author",
    "author.dev": "Dev",
    "author.email": "Email",
    "tip.copyEmail": "Copy the email to the clipboard",

    "foot": "Jobs only run while the black window (the server) is open — "
            "closing it stops everything running, ffmpeg included. A part-"
            "downloaded file still resumes next time. This page cannot see "
            "runs started from Start.cmd.",
}

STRINGS = {"vi": VI, "en": EN}
DEFAULT = "vi"


def check():
    """Both languages carry the same keys, or say which ones they do not.

    The failure this catches is the one that happens: a string added to the
    page in one language and forgotten in the other, which shows up as a blank
    label only when somebody switches.
    """
    missing = {}
    keys = set().union(*(set(d) for d in STRINGS.values()))
    for lang, table in STRINGS.items():
        gap = sorted(keys - set(table))
        if gap:
            missing[lang] = gap
    if missing:
        raise ValueError(f"i18n keys missing: {missing}")
    return len(keys)


check()
