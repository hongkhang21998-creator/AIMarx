"""WhereMyTokens-inspired dashboard, adapted to AIMarx's local Ollama metrics.

Theme/layout adapted from jeongwookie/WhereMyTokens (MIT, copyright 2026).
See docs/third-party/WhereMyTokens-LICENSE.txt and the integration handoff.
"""
from datetime import datetime
from html import escape
from .token_usage import LOCAL_TZ


STYLE = '''
:root{color-scheme:dark;--bg:#0d0f13;--card:#161920;--row:#1e2230;--border:#303543;
--text:#e8eaf0;--dim:#a5abbc;--accent:#2dd4bf;--input:#60a5fa;--output:#34d399;--gold:#fbbf24}
:root[data-theme=light]{color-scheme:light;--bg:#f4f4f8;--card:#fff;--row:#ebebf2;
--border:#d0d0e0;--text:#1a1a30;--dim:#505070;--accent:#0f766e;--input:#2a68b8;--output:#287428;--gold:#925900}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px system-ui,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}a:focus-visible,summary:focus-visible{outline:3px solid var(--gold);outline-offset:4px}
.shell{max-width:1200px;margin:auto;padding:28px}.top,.heading,.section-head,.model-head,.foot{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap}
.top{padding-bottom:22px;border-bottom:1px solid var(--border)}.brand{font-size:24px;font-weight:750;color:var(--text)}.brand span{color:var(--gold)}
nav,.actions,.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center}nav a,.button,.filters a{padding:9px 13px;border-radius:7px;border:1px solid transparent}
nav a[aria-current],.filters a[aria-current]{background:var(--row);border-color:var(--border);color:var(--accent)}
.button{border-color:var(--border);color:var(--text);background:var(--card)}.heading{margin:30px 0 22px}h1{font-size:30px;letter-spacing:-.8px;margin:0 0 8px}h2{font-size:16px;margin:0}p{line-height:1.65}.sub,.muted{color:var(--dim)}.sub{margin:0}.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;color:var(--dim);font-weight:650}
.badge{border:1px solid var(--border);border-radius:5px;padding:4px 8px;font-size:12px;color:var(--accent);white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card,.panel{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:21px}
.value{font:600 32px ui-monospace,Consolas,monospace;letter-spacing:-1px;margin:18px 0 12px;overflow-wrap:anywhere}.value.accent{color:var(--accent)}.value.input{color:var(--input)}.value.output{color:var(--output)}.small{font-size:12px;color:var(--dim);line-height:1.6}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;background:var(--accent)}.dot.input{background:var(--input)}.dot.output{background:var(--output)}
.coverage{padding:13px 16px;margin:16px 0 22px;background:var(--row);border-radius:8px;font-size:13px;line-height:1.7;color:var(--dim)}
.grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:16px;margin:16px 0}.section-head{margin-bottom:22px}.section-head .small{margin:0}
.chart{height:158px;display:flex;align-items:stretch;gap:6px;margin:22px 0 8px}.column{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:flex-end;border-bottom:1px solid var(--border)}.bar{display:block;min-height:0;background:var(--accent);border-radius:3px 3px 0 0}.axis{display:flex;justify-content:space-between;color:var(--dim);font:11px ui-monospace,monospace}.legend{margin-top:19px;display:flex;gap:20px;flex-wrap:wrap;font-size:12px;color:var(--dim)}
.heatmap{display:grid;grid-template-columns:repeat(28,minmax(0,1fr));gap:4px;margin:22px 0 14px}.cell{aspect-ratio:1;border-radius:2px;background:var(--row);border:1px solid var(--border)}.level1{background:#134e4a}.level2{background:#0f766e}.level3{background:#0d9488}.level4{background:#2dd4bf}
.model{padding:16px 0;border-bottom:1px solid var(--border)}.model:first-of-type{padding-top:0}.model:last-child{border-bottom:0}.model-name{font-weight:600;color:var(--accent);overflow-wrap:anywhere;max-width:100%}.mono{font-family:ui-monospace,Consolas,monospace}.track{height:4px;margin:12px 0;background:var(--row);border-radius:3px;overflow:hidden}.fill{height:100%;background:var(--accent)}
.empty{padding:26px 10px;text-align:center}.empty strong{display:block;font-size:17px;margin-bottom:10px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}th{text-align:left;font-weight:500;color:var(--dim);font-size:12px}th,td{padding:14px 12px;border-bottom:1px solid var(--border)}td:first-child,th:first-child{padding-left:0}td.num,th.num{text-align:right}.state{font-size:11px;padding:4px 7px;background:var(--row);border-radius:4px}.state.failed,.state.pending{color:var(--gold)}details{margin-top:20px;line-height:1.8;color:var(--dim)}summary{cursor:pointer;color:var(--text)}.foot{padding:24px 0 0;color:var(--dim);font-size:12px}.notice{color:var(--gold)}
@media(max-width:850px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.grid{grid-template-columns:1fr}.shell{padding:20px}.heatmap{grid-template-columns:repeat(21,minmax(0,1fr))}}
@media(max-width:480px){.shell{padding:14px}.top{gap:15px}.brand{font-size:21px}h1{font-size:25px}.card,.panel{padding:16px}.cards{gap:9px}.value{font-size:25px}.filters a{padding:9px}.heatmap{grid-template-columns:repeat(14,minmax(0,1fr))}}
'''


def number(value):
    return "—" if value is None else f"{value:,}".replace(",", ".")


def combined(row):
    if row["input_tokens"] is None and row["output_tokens"] is None:
        return None
    return (row["input_tokens"] or 0) + (row["output_tokens"] or 0)


def local_time(value):
    return datetime.fromisoformat(value).astimezone(LOCAL_TZ).strftime("%d/%m/%Y %H:%M") if value else "Chưa có lượt gọi"


def render_dashboard(data, theme="dark"):
    theme = "light" if theme == "light" else "dark"
    period, totals = data["period"], data["totals"]
    labels = {"today": "Hôm nay", "7d": "7 ngày", "30d": "30 ngày", "all": "Tất cả"}
    link = lambda p=period, t=theme: f"/usage?period={p}&amp;theme={t}"
    filters = ''.join(f'<a href="{link(p)}"' + (' aria-current="page"' if p == period else '') + f'>{label}</a>' for p, label in labels.items())
    speed = totals["timed_tokens"] * 1e9 / totals["timed_ns"] if totals["timed_ns"] else None
    speed_text = f"{speed:.1f}" if speed is not None else "—"
    cards = ''.join(f'<section class="card"><div class="eyebrow">{label}</div><div class="value {color}">{value}</div><div class="small">{hint}</div></section>' for label, value, color, hint in [
        ("Token đã ghi nhận", number(combined(totals)), "accent", f'{number(totals["calls"])} lượt gọi Ollama'),
        ("Token đầu vào", number(totals["input_tokens"]), "input", "Nội dung và chỉ dẫn gửi vào model"),
        ("Token đầu ra", number(totals["output_tokens"]), "output", "Token model sinh, do Ollama báo"),
        ("Tốc độ sinh · token/giây", speed_text, "", "Tính từ token và thời gian sinh có số liệu"),
    ])
    incomplete = totals["incomplete"] or 0
    coverage = (f'<span class="notice">{incomplete} lượt chưa đủ số token.</span> Tổng chỉ cộng số đã nhận; có thể thấp hơn thực tế.'
                if incomplete else ("Các lượt trong bộ lọc đều có đủ số token vào/ra." if totals["calls"] else "Chưa ghi nhận lượt gọi Ollama trong khoảng này."))
    coverage += f' Lỗi kết nối/phản hồi: {totals["failed"] or 0} · Chưa kết thúc: {totals["pending"] or 0}.'
    activity = data["activity"]
    peak = max((combined(day) or 0 for day in activity), default=0)
    bars = ''
    cells = ''
    for day in activity:
        value = combined(day)
        tip = escape(f'{day["day"]}: {number(value)} token đã ghi nhận; {day["calls"]} lượt gọi', quote=True)
        height = 100 * (value or 0) / peak if peak else 0
        bars += f'<div class="column" title="{tip}" aria-label="{tip}"><span class="bar" style="height:{height:.2f}%"></span></div>'
        level = min(4, max(1, round(height / 25))) if height else 0
        cells += f'<span class="cell level{level}" title="{tip}" aria-label="{tip}"></span>'
    activity_title = "Hoạt động · 84 ngày gần nhất" if period == "all" else "Hoạt động theo ngày"
    chart = (f'<div class="heatmap" role="img" aria-label="Mức dùng token trong 84 ngày, có bảng dữ liệu bên dưới">{cells}</div>' if period == "all" else
             f'<div class="chart" role="img" aria-label="Token ghi nhận theo ngày, có bảng dữ liệu bên dưới">{bars}</div>')
    if not any(day["calls"] for day in activity):
        chart = '<div class="empty"><strong>Chưa có hoạt động trong khoảng này</strong><p class="small">Trích xuất một tài liệu bằng Ollama để bắt đầu ghi nhận.<br>Chế độ demo và chỉnh sửa thủ công không dùng token.</p><a class="button" href="/">Mở kho tài liệu</a></div>'
    chart += f'<div class="axis"><span>{activity[0]["day"]}</span><span>{activity[-1]["day"]}</span></div>'
    chart += '<div class="legend"><span><i class="dot"></i>Token vào + ra đã ghi nhận</span><span>Giờ Việt Nam · UTC+7</span></div>'
    day_rows = ''.join(f'<tr><td>{day["day"]}</td><td>{day["calls"]}</td><td>{number(day["input_tokens"])}</td><td>{number(day["output_tokens"])}</td></tr>' for day in activity)
    chart += f'<details><summary>Xem số liệu từng ngày</summary><div class="table-wrap"><table><thead><tr><th>Ngày</th><th>Lượt gọi</th><th>Token vào</th><th>Token ra</th></tr></thead><tbody>{day_rows}</tbody></table></div></details>'
    models = ''
    total = combined(totals) or 0
    for row in data["models"]:
        share = 100 * (combined(row) or 0) / total if total else 0
        models += f'<div class="model"><div class="model-head"><span class="model-name">{escape(row["model"])}</span><span class="mono">{number(combined(row))}</span></div><div class="track"><div class="fill" style="width:{share:.2f}%"></div></div><div class="small"><i class="dot input"></i>Vào {number(row["input_tokens"])} &nbsp; <i class="dot output"></i>Ra {number(row["output_tokens"])} · {row["calls"]} lượt</div></div>'
    models = models or '<div class="empty"><strong>Chưa có số liệu model</strong><p class="small">Tên model sẽ xuất hiện sau lần gọi đầu tiên.</p></div>'
    states = {"received": "Đã nhận phản hồi", "failed": "Lỗi kết nối/phản hồi", "pending": "Chưa kết thúc"}
    rows = ''
    for row in data["recent"]:
        duration = f'{row["total_ns"] / 1e9:.2f} s' if row["total_ns"] is not None else "—"
        rows += f'<tr><td class="mono">{local_time(row["created"])}</td><td>{escape(row["model"])}</td><td class="num mono">{number(row["input_tokens"])}</td><td class="num mono">{number(row["output_tokens"])}</td><td class="num mono">{duration}</td><td><span class="state {row["state"]}">{states[row["state"]]}</span></td></tr>'
    rows = rows or '<tr><td colspan="6" class="muted">Chưa có lượt gọi để hiển thị.</td></tr>'
    other_theme, theme_label = ("light", "Giao diện sáng") if theme == "dark" else ("dark", "Giao diện tối")
    return f'''<!doctype html><html lang="vi" data-theme="{theme}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Thống kê token · AIMarx</title><style>{STYLE}</style></head><body><div class="shell">
<header class="top"><a class="brand" href="/">AI<span>Marx</span> <span class="badge">Ollama · local</span></a><nav aria-label="Điều hướng chính"><a href="/">Kho tài liệu</a><a href="/tasks">Sổ công việc</a><a href="{link()}" aria-current="page">Thống kê token</a></nav></header>
<main><div class="heading"><div><div class="eyebrow">MỨC SỬ DỤNG AI</div><h1>Token của bạn đi đâu?</h1><p class="sub">Theo dõi mức sử dụng Ollama ngay trên máy của bạn.</p></div><div class="actions"><a class="button" href="{link(t=other_theme)}">{theme_label}</a><a class="button" href="{link()}">Làm mới</a></div></div>
<div class="section-head"><div class="filters" aria-label="Khoảng thời gian">{filters}</div><span class="small">Cập nhật {local_time(data["as_of"])} · UTC+7</span></div>
<div class="cards">{cards}</div><div class="coverage">{coverage}</div>
<div class="grid"><section class="panel"><div class="section-head"><h2>{activity_title}</h2><span class="badge">TOKEN</span></div>{chart}</section><section class="panel"><div class="section-head"><h2>Sử dụng theo model</h2><span class="small">{labels[period]}</span></div>{models}</section></div>
<section class="panel"><div class="section-head"><h2>Lượt gọi gần đây</h2><span class="small">Tối đa 50 lượt trong bộ lọc</span></div><div class="table-wrap"><table><thead><tr><th>Thời điểm · UTC+7</th><th>Model yêu cầu</th><th class="num">Token vào</th><th class="num">Token ra</th><th class="num">Thời gian Ollama</th><th>Phản hồi</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<details><summary>Cách đọc số liệu và phạm vi thống kê</summary><p>Bắt đầu ghi nhận: {local_time(data["first"])}. Chỉ gồm các lần AIMarx gọi Ollama qua luồng trích xuất từ khi cài tính năng. Không truy hồi lịch sử cũ, không tính demo, thao tác thủ công hoặc các lần gọi từ ứng dụng khác.</p><p>Dấu — nghĩa là chưa có số liệu, không phải 0. Tổng cộng các trường đã nhận nên có thể chưa đầy đủ. “Đã nhận phản hồi” không có nghĩa trích xuất đúng, đã lưu phiếu hay được người dùng duyệt: token vẫn tính khi dữ liệu sinh bị kiểm tra nguồn từ chối. “Chưa kết thúc” có thể là đang chạy hoặc bị gián đoạn; không tự gọi lại model.</p><p>Tốc độ sinh = tổng token đầu ra có thời gian sinh hợp lệ / tổng thời gian sinh tương ứng; không gồm nạp model hoặc xử lý đầu vào. Không đo chi phí điện, tiền API, quota tài khoản hay hiệu quả cache. Kho thống kê chỉ lưu thời điểm, model, trạng thái và các số đếm; không lưu nội dung tài liệu, prompt, câu trả lời hoặc thông tin đăng nhập.</p></details></main>
<footer class="foot"><span><i class="dot"></i>Số liệu lưu cùng kho AIMarx · không đồng bộ cloud</span><span>UX/UI chuyển thể từ <a href="https://github.com/jeongwookie/WhereMyTokens" rel="noreferrer">WhereMyTokens</a> · MIT</span></footer></div></body></html>'''
