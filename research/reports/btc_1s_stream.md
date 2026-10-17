# Nến BTC 1 giây và nhạc streaming

Đo ngày 2026-10-17. Pipeline sonify hiện tại (`backend/app/sonify`) nhận cả phiên OHLC rồi mới viết một bản 30 ô nhịp. Bản streaming cần nguồn nến đóng từng giây và một máy trạng thái chỉ nhìn quá khứ.

## Kết luận

Binance spot `BTCUSDT` có nến 1 giây, không cần API key. Trên mirror công khai, nến đóng tới máy này khoảng 50 ms sau mốc sự kiện và khoảng 70–85 ms sau thời điểm nến khép. Đó là độ trễ của đường truyền, chưa tính 1 giây phải chờ nến đóng.

Nếu mỗi nến đóng thành một phách và tempo khóa 60 BPM, người nghe chậm giá vừa khớp khoảng 1,2 giây. Phần lớn khoảng đó là bản thân nến, không phải mạng.

Nến chính thức dừng ở 1 giây. Muốn 2 hoặc 4 điểm trong một giây thì tự cắt dòng `btcusdt@aggTrade` thành ô 500 ms hoặc 250 ms. Mẫu 8 giây, thị trường gần như đứng, có 4–12 lệnh gộp mỗi giây. Mọi ô 500 ms và 250 ms đều có ít nhất một lệnh. Ô 100 ms trống khoảng một nửa. Phát 4 nốt trong một giây thì độ trễ tới tai còn khoảng 0,4 giây, vì không phải chờ cả nến 1 giây đóng.

OKX `candle1s` dùng được khi Binance bị chặn, nhưng nến đóng tới chậm hơn khoảng 1,1 giây so với mốc khép. Bybit và Coinbase không có nến 1 giây chính thức.

## Đo từ máy này

`api.binance.com` và `api1.binance.com` trả HTTP 451. Hai host market-data công khai thì mở:

| Đường | Kết quả |
|---|---|
| `wss://data-stream.binance.vision/ws/btcusdt@kline_1s` | 9/9 message là nến đã đóng (`k.x = true`). Trễ so với `E`: min 48 ms, p50 51 ms, max 51 ms. Trễ so với `k.T`: 66–86 ms |
| `GET https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1s&limit=3` | RTT khoảng 150–420 ms. Nến mới nhất đã đóng, tuổi tính từ `closeTime` khoảng 145 ms ở lần gọi sát |
| `wss://ws.okx.com:8443/ws/v5/business` kênh `candle1s` / `BTC-USDT` | Có cả nến đang hình thành (`confirm=0`) và nến đóng (`confirm=1`). Nến đóng tới khoảng 1,1–1,2 giây sau mốc mở + 1 giây |
| `GET https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1s` | RTT khoảng 140 ms khi gọi được. Lần gọi sát sau đó bị 403, không nên dựa vào REST này để poll |

REST Binance trả về nến đã đóng, không phải nến đang chạy. Poll 1 giây một lần dễ nuốt mất một giây khi RTT cộng lịch gọi vượt quá nhịp. WebSocket là đường phát.

## Hợp đồng Binance spot

Tài liệu: [web-socket-streams.md](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md), mục Kline/Candlestick Streams.

- Stream: `<symbol>@kline_1s`. Với BTC: `btcusdt@kline_1s`.
- Nhịp đẩy của interval `1s` là 1000 ms. Các interval khác là 2000 ms. Trên mẫu 8 giây, mỗi giây đúng một message và message đó đã là nến đóng. Không có bản cập nhật giữa giây.
- Trường dùng cho nhạc: `k.t` (mở, ms), `k.c` (giá đóng), `k.v` (khối lượng base), `k.n` (số lệnh khớp), `k.x` (đã đóng). Chỉ phát khi `k.x` là true để một giây thị trường thành một phách, không viết lại nốt đang kêu.
- Giới hạn kết nối: tối đa 5 message phía client mỗi giây (kể cả ping/pong), 1024 stream mỗi socket, 300 kết nối mới mỗi 5 phút mỗi IP. Một socket nghe `btcusdt@kline_1s` nằm rất xa các trần này.
- Lịch sử ngắn: `GET /api/v3/klines?symbol=BTCUSDT&interval=1s&limit=1000` trên `data-api.binance.vision`. 1000 nến là khoảng 16 phút 40 giây.
- Lịch sử dài, đã kiểm tra HEAD 200: `https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1s/BTCUSDT-1s-2026-10-16.zip` (khoảng 2,2 MB) và file tháng `BTCUSDT-1s-2026-09.zip` (khoảng 70 MB). Đủ để replay cả phiên trước khi nối live.

USD-M futures không nằm trong lựa chọn này. Tài liệu kline futures liệt kê từ 1 phút và đẩy mỗi 250 ms cho nến đang mở, không có interval `1s`.

## OKX khi Binance đóng

- WebSocket business, không cần login cho kênh nến: `wss://ws.okx.com:8443/ws/v5/business`.
- Subscribe: `{"op":"subscribe","args":[{"channel":"candle1s","instId":"BTC-USDT"}]}`.
- Mỗi dòng: `[ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]`. `confirm = "1"` là nến đóng. `ts` là thời điểm mở.
- Client phải gửi `ping` dạng text theo nhịp OKX (khoảng 20 giây). Mất kết nối thì subscribe lại.

Độ trễ thêm khoảng một giây so với Binance là chấp nhận được nếu tiêu chí là "không nhiều quá", và vẫn xấu hơn Binance khi cả hai cùng sống.

## Nguồn không dùng cho khung 1 giây

| Nguồn | Vì sao bỏ |
|---|---|
| Bybit `kline.{interval}.BTCUSDT` | Interval nhỏ nhất trong tài liệu là 1 phút |
| Coinbase Advanced Trade candles | Granularity nhỏ nhất 60 giây. Muốn 1 giây thì phải tự gom trade |
| Binance `btcusdt@trade` thô | Cùng một lệnh taker bị tách nhiều print. `aggTrade` gộp chúng lại, ít message hơn mà vẫn là giá khớp |
| Poll REST 1 giây | Trễ bằng RTT và dễ mất nến |

## Nhỏ hơn 1 giây

Tài liệu kline spot không có interval dưới `1s`. Depth có nhịp 100 ms, nhưng đó là sổ lệnh, không phải giá khớp.

Dòng dùng được là aggregate trade, realtime:

`wss://data-stream.binance.vision/ws/btcusdt@aggTrade`

Mỗi message là một lệnh taker đã gộp: `T` thời điểm khớp (ms), `p` giá, `q` khối lượng. Đo cùng máy với nến 1 giây: 54 message trong 7,8 giây, trễ so với `T` min 47 ms, p50 48 ms, p95 54 ms.

Cách nén vào một giây nhạc: chia đồng hồ thành ô cố định, lấy giá khớp cuối và tổng khối lượng trong ô. Ô trống thì giữ giá trước, khối lượng 0. Không phát từng lệnh thành một nốt. Lúc BTC chạy nhanh có thể hàng trăm lệnh mỗi giây, giai điệu sẽ cụm rồi ngắt.

| Ô | Điểm trong 1 giây nhạc | Mẫu 7 giây đầy đủ | Nốt, tempo 60 |
|---|---|---|---|
| 500 ms | 2 | 14/14 ô có lệnh | móc đơn, mỗi nốt 500 ms |
| 250 ms | 4 | 28/28 ô có lệnh | móc kép, mỗi nốt 250 ms |
| 100 ms | 10 | 39/70 ô có lệnh, 31 ô trống | dày hơn mức tai tách được, nhiều ô phải giữ nốt cũ |

Trong mẫu này giá gần như không đổi: biên độ trong ô chỉ 0–0,01 USD. Bốn điểm vẫn có ích khi giá chạy. Lúc đứng, bốn nốt cùng cao độ là đúng với thị trường, không phải lỗi dữ liệu.

Độ trễ tới tai với ô 250 ms:

| Khúc | Thời gian |
|---|---|
| Chờ ô khép | 250 ms |
| Binance tới server | khoảng 50 ms |
| Lượng hóa + gửi sự kiện | vài ms |
| Bộ đệm phát | 100–200 ms |
| Tổng so với giá trong ô | khoảng 0,4–0,5 giây |

Lịch sử để replay cùng lưới: `https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-10-16.zip` (HEAD 200, khoảng 12,8 MB). Zip nến `1s` không tái tạo được 4 điểm trong giây.

## Cách phát nhạc bám nến

Renderer hiện tại không chạy từng nến được. `MUSICAL_BARS = 30` và `plan_slots` chọn hợp âm bằng quy hoạch trên cả bản. `session_bars` cũng cắt theo phiên HOSE, trong khi BTC chạy 24/7.

Máy streaming nên tách khỏi bản 30 ô:

1. Một process giữ socket `btcusdt@aggTrade`, cắt ô 250 ms hoặc 500 ms theo `T`, lấy giá khớp cuối và tổng `q`. Ô trống giữ giá trước. Nến `kline_1s` chỉ còn là đường thô, một điểm mỗi giây.
2. Trạng thái chỉ nhân quả: MA trên N giá đóng vừa rồi (cửa sổ 20 nếu muốn cùng `MA_WINDOW`), regime của cửa sổ đó, hợp âm hiện tại. Hợp âm đổi theo regime và bậc lượng hóa của giá, không nhìn tương lai.
3. Khóa tempo với đồng hồ thị trường, không với số lệnh. Một giây tường đồng hồ luôn thành một giây nhạc. Bên trong giây đó đặt 1, 2 hoặc 4 nốt tùy lưới 1000 / 500 / 250 ms. Tempo nhanh hơn sẽ hết dữ liệu. Tempo chậm hơn phải xếp hàng và ngày càng trễ.
4. Đẩy sự kiện nốt (pitch, velocity từ volume, duration, chord) qua WebSocket của backend. Không render MusicXML cho đường live.

Độ trễ tới tai, cộng dồn:

| Khúc | Thời gian |
|---|---|
| Chờ nến 1 giây đóng | 1000 ms |
| Binance tới server (đã đo) | khoảng 70–85 ms |
| Lượng hóa + gửi sự kiện | vài ms |
| Bộ đệm phát để khỏi nứt tiếng | 100–200 ms |
| Tổng so với giá trong giây đó | khoảng 1,2–1,3 giây |

App Expo 54 hiện không có thư viện synth. `expo-av` / phát file không giữ nhịp nốt rời. Hướng hợp với dev client là synth trên máy (Web Audio API của `react-native-audio-api` hoặc soundfont native): server gửi nốt, máy kêu. Render WAV từng giây rồi phát file thêm một bộ đệm và dễ hở giữa các đoạn. HLS thêm 2–5 giây nữa, thừa so với một người nghe một dòng nốt.

Replay zip `aggTrades` và socket live dùng chung một hàm "ô đóng → sự kiện". Zip nến `1s` chỉ đủ cho lưới một điểm mỗi giây. Khi live reconnect, lấy lại các lệnh từ `GET /api/v3/aggTrades` theo `startTime` rồi mới theo `T` mới.
