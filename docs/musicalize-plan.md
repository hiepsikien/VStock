# Musicalize — kế hoạch app nghe nhạc

Web app nghe nhạc trên engine sonify và API đang có. App Expo giữ vai trò terminal cổ phiếu. Musicalize là mặt nghe mới. Tên sản phẩm là Musicalize. Module trong repo vẫn là `sonify` và `vstock`.

Tài liệu này chốt sản phẩm v1, phong cách, và tech stack của mặt nghe. Tách dịch vụ, hàng đợi MuseScore và cache audio vẫn viết sau, khi phạm vi lớn hơn hai phòng.

## Màn nghe

Người nghe chọn nhạc trước. Mã và ngày giao dịch vẫn hiện, vì đó là dữ liệu đã sinh ra bài. Giá chỉ là thang trên trục dọc của chart. Phần trăm, khối lượng, vốn hóa, mở/cao/thấp và kết quả kinh doanh không đặt lên màn này.

Thứ tự trên màn:

1. **Thể loại, nhạc cụ, nghệ sĩ.** Đây là điều khiển chính.
2. **Tên bài, chương, giọng, nhịp.** `pieceCopy` trong `src/sonify/program.ts` đã ghép các tên này.
3. **Mã và ngày**, cùng dòng danh tính của bài. Bài dài hiện khung `1W`, `1M`, `3M`, `1Y`.
4. **Sân khấu.** Đường dữ liệu và playhead để tai và mắt đi cùng một nhịp.

Nhãn thể loại và nhạc cụ lấy từ `ENSEMBLE_ROWS` trong `src/api/client.ts`:

| Bước | Người nghe thấy | Trong engine |
|---|---|---|
| Thể loại | Giao hưởng, Jazz, Tối giản, Ambient, Guitar | `symphony`, `jazz`, `minimalist`, `ambient`, `guitar` |
| Nhạc cụ | Dây / Gỗ / Đồng; Combo / Soul / Organ; Synth / Mallet / Guitar thép; Kính / Hơi / Hợp xướng | Hàng ensemble của từng thể loại |
| Nghệ sĩ | Bach, Sor, Barrios, Lobos, Brouwer | Chỉ khi thể loại là Guitar |

Tên bài đã có: Bagatelle, Fantasia, Divertimento, Quintet, Serenade, Jazz, Set, Etude, Cycle, Prelude, Nocturne, Suite. Chương dài mang Allegretto, Siciliana, Minuet, Swing, Ballad, Waltz, Adagio, Finale, hoặc điệu guitar như Sarabande, Tremolo, Prelude. Một dòng trong tủ nhạc đọc tên thể loại và giọng trước, mã và ngày đứng cạnh. Ví dụ tên ghép sẵn là `Bagatelle VNM 20/1 in E-flat`.

## Sân khấu giữ nguyên

`PriceChart`, `Sparkline`, `PieceTitle` và playhead của `SessionRecap` / `SpanRecap` là sân khấu. Musicalize nhúng khối này, không vẽ chart mới.

Giữ nguyên:

- Đường giá, vùng tô, nét chưa phát mờ đi khi đang nghe.
- Vạch playhead theo thời gian audio, nhãn giờ trên đầu vạch.
- Trước khi nghe: tên bài, nhạc cụ, chương nằm giữa sân khấu.
- Khi đang phát: tên bài và chương ở góc dưới sân khấu.
- Trục giá là cao nhất và thấp nhất, chữ phụ bên phải.
- Khung `1D`, `1W`, `1M`, `3M`, `1Y` trên màn mã nằm trong `PriceChart` (`RANGES`, kèm `5Y`). Trên Musicalize, chọn khung và chọn ngày của bảy phiên `1D` nằm ở cột trái, cùng dòng mã. Sân khấu không vẽ thanh `RANGES`, nên `5Y` không xuất hiện. Đang phát không có khung ngày. Sân khấu lúc đó là `Sparkline` và trục giá.
- Chương dài vẫn phóng đúng đoạn đang nghe (`chartFocus` khi `audible`).
- Luồng bấm Nghe, backend soạn file, playhead dùng `mapDurationSec` và `ambientDailyCandleIndexAt`.

Đài live hôm nay là `backend/app/sonify/player.html`, một canvas riêng với ô giá lớn. Trên Musicalize, băng crypto gắn vào cùng `Sparkline`: đường giá, playhead, trục min/max. Mã cặp nằm trên dòng đài.

## UI quanh sân khấu

Màn mã hiện mở bằng giá lớn và phần trăm, rồi mới tới chart. Dưới chart, thể loại và nhạc cụ là hai hàng chip cùng cỡ. Chip ngày kèm phần trăm xanh đỏ. Nút Nghe ghép giọng với nhãn tính cách phiên (`Tăng giá`, `Bán tháo`, `Giằng co`, `Tích lũy` trong `CHARACTER_LABEL`).

| Chỗ | Hiện trên màn mã | Trên Musicalize |
|---|---|---|
| Mở màn | Mã lớn, giá lớn, phần trăm, sàn | Vào thẳng sân khấu. Mã và ngày đọc trên tên bài và trên dòng chọn bài |
| Chọn nhạc | Hai hàng chip ngang nhau dưới chart | Hàng thể loại đứng trước, to hơn. Hàng dưới là nhạc cụ. Guitar thì hàng dưới là nghệ sĩ |
| Chọn ngày | Thứ, ngày, và phần trăm phiên | Thứ và ngày |
| Nút nghe | Nghe · giọng · Tăng giá | Nghe, Tạm dừng, Nghe lại, thanh kéo |
| Humanize, Màu | Ngang hàng với chọn nhạc | Trong mục tùy chọn nghe |
| Sân khấu | Chart, playhead, tên bài, trục | Nguyên khối, thêm kéo playhead |

## Phong cách

Phòng thu tối, hướng Cyberpunk-Fintech. Nền `#0D0F12`. Ba điểm nhấn, mỗi màu một việc: cyan `#3EE0E0` là dữ liệu, magenta `#E040A0` là tiếng, amber `#F5B942` là chỗ đang nghe. Chữ chính `#F4F1EA`, chữ phụ `#9AA3AD`. Mặt cột `#14181E`. Terminal cổ phiếu giữ `src/theme.ts`. Musicalize có bảng màu riêng, phẳng, không gradient, không đổ bóng, không đĩa than.

Chữ sans. Tên bài 22 semibold giữa sân khấu, như `PieceTitle`. Thể loại 15. Mã, ngày và số trên trục 13, `tabular-nums`. Giá lớn 40 và phần trăm không có trên vỏ.

Hai cột từ khoảng 960px. Cột trái hẹp, để chọn. Cột phải rộng và chia hai hàng: sân khấu phía trên, cụm điều khiển phía dưới. Sân khấu lấy hết bề ngang của cột phải, nên không bị một cột console làm hẹp ở giữa. Dưới mức đó, ba phần xếp dọc theo thứ tự trái rồi phải: chọn mã, sân khấu, cụm điều khiển.

| Phần | V1 | Để dành cùng chỗ |
|---|---|---|
| Cột trái, chọn đối tượng nghe | Công tắc trên cùng cột: Nghe lại hoặc Đang phát. Nghe lại liệt kê mã chứng khoán, mỗi dòng kèm ngày hoặc khung. Đang phát liệt kê top 10 mã crypto. Đổi công tắc thì đổi danh sách và đổi cụm điều khiển bên dưới sân khấu | Loại chuỗi Price / Volume / Biometrics / Weather. Hôm nay engine chỉ đọc giá đóng và khối lượng của nến. Volume đã thành lực tiếng, chưa phải một chuỗi người nghe chọn. Biometrics và thời tiết chưa có cổng |
| Cột phải, hàng trên, sân khấu | Đường giá và playhead. Với phiên `1D`, `RecapManifest.peaks` vẽ magenta trong cùng khung, hòa vào đường cyan. Bài `1W`–`1Y` chưa có `peaks` trên `SpanMovement`, nên sân khấu chỉ có đường giá cho đến khi API trả sóng. Kéo playhead trên sân khấu chỉ tua trong đoạn đang nhìn thấy | Nến là một cách vẽ sau, trên cùng playhead. Thêm `peaks` cho span là việc sau, để sóng cũng hiện trên bài dài |
| Cột phải, hàng dưới, cụm điều khiển | Theo công tắc bên trái. Nghe lại: thể loại, nhạc cụ, nghệ sĩ, Nghe, Tạm dừng, Nghe lại, và thanh thời gian của cả tác phẩm. Đang phát: bốn thể loại, Nghe và Tạm dừng. Chip đang chọn dùng magenta | Pan sân khấu và xuất widget. Cyberpunk như một thể loại. Bach đã là nghệ sĩ Baroque của Guitar, chưa phải một lăng kính riêng tên Baroque |

Đèn tập tai, khi làm, dùng đúng ba màu này: amber trên playhead giai điệu, magenta trên vùng tô thanh khoản, cyan trên chấm breakout và đoạn scale.

## Tech stack

Mặt nghe ở trong repo này, chạy Expo web. Sân khấu, `expo-audio` và `recapCursor` đã là React Native. Một app Vite riêng sẽ phải vẽ lại `Sparkline`.

| Tầng | Chọn | Lý do |
|---|---|---|
| Web | Expo SDK 58, React Native 0.88, lệnh `npm run web` đã có | `app.config.ts` đã khai `web`. `PriceChart` dùng `react-native-svg`. Bảng màu Musicalize truyền vào chart, `theme.ts` của terminal giữ nguyên |
| Gói cần thêm khi làm lát A | `react-dom`, `react-native-web` | Expo web cần hai gói. Hiện chúng chỉ là peer tùy chọn trong lockfile |
| Màn | `App.web.tsx` cạnh `App.tsx`, rồi nhóm `src/musicalize/` | `index.ts` import `./App`. Metro chọn `App.web.tsx` khi bundle web và giữ `App.tsx` cho iOS và Android. Terminal không vào bundle web |
| Logic dùng chung | `src/sonify/program.ts`, `src/utils/recapCursor.ts`, `ENSEMBLE_ROWS` | Tên bài, playhead và nhãn nhạc đã khóa bằng test |
| API | FastAPI hiện tại | `recap`, `span`, WebSocket `/v1/sonify/ws`. Không thêm service |
| Replay | File m4a qua `expo-audio`, `seekTo` | Native đã seek trên sóng peaks. Lát A xác nhận `seekTo` trên web trước khi khóa transport |
| Live | Web Audio, tách khỏi `player.html` | Bucket 250 ms không đi qua MuseScore. Chart của đài vẫn là `Sparkline` |
| Chỗ đứng | Cùng origin với API | `sonify.py` đóng socket khi `Origin` khác host |

Backend giữ MuseScore, ffmpeg và SQLite trên GCE. Export web là file tĩnh phục vụ cùng host API. Auth, Postgres, Next và việc tách sonify khỏi API không thuộc v1.

## Nghe lại và nghe từ một chỗ

Replay là file audio. Một phiên là một file. Bài dài là một file mỗi chương. Người nghe điều khiển file đó như một bài nhạc. Đài live không tua, vì nốt phát theo lệnh đang khớp.

| Việc | Hành vi |
|---|---|
| Nghe / Tạm dừng | Đang phát thì dừng tại chỗ. Bấm tiếp thì đi tiếp từ đúng giây đó |
| Nghe lại | Một phiên: về đầu file. Bài nhiều chương: về đầu chương đang nghe. Lần bấm nữa, hoặc khi bài đã hết, về đầu cả tác phẩm |
| Nghe từ một chỗ | Kéo thanh thời gian, hoặc kéo playhead trên sân khấu. Audio và chart đứng cùng một điểm |
| Hết bài | Playhead dừng ở cuối. Nghe lại đưa về đầu. Kéo thanh thì nghe từ chỗ vừa chọn |

Hiện trên app:

- Phiên `1D` có sóng peaks bấm để nhảy giây (`RecapPlayer.seek`). Nút chỉ ghi Nghe hoặc Tạm dừng. Playhead trên chart là vạch hiển thị, chưa kéo được.
- Bài `1W`–`1Y` khi đang phát chỉ có Tạm dừng và Tiếp tục (`MovementPlayer`). Nghe lại hiện khi cả bài đã chạy xong, và `replay()` luôn về chương đầu. Trong chương không seek.

Sóng `peaks` và thanh kéo là hai việc. `peaks` của phiên `1D` vẽ trên sân khấu, magenta, hòa vào đường giá. Thanh kéo nằm trong cụm điều khiển. Phiên `1D` dùng cùng mảng `peaks` cho thanh đó. Bài `1W`–`1Y` chưa có `peaks` trong `SpanMovement`, nên thanh của chương là thanh phẳng theo `durationSec`. Một thanh nữa phủ cả tác phẩm, cộng `restAfterSec` giữa chương. Thanh này là chỗ tua sang chương khác. Lát B không chờ API thêm `peaks`.

Kéo thanh audio ra một giây, rồi playhead lấy nến từ `ambientDailyCandleIndexAt` (phiên `1D`) hoặc `spanCandleIndexAt` (bài dài). Kéo vạch trên sân khấu thì ngược lại. Tỷ lệ `r` nằm trên các nến giá đang hiện, không nằm trên ô warm-up và cool-down. Hai đầu khung gộp nhiều ô vào nến đầu và nến cuối, nên seek theo `r * durationSec` sẽ kẹt playhead ở hai đầu. Giây đích là phần thân giá:

- Phiên `1D`, khung 34 ô: `introEnd = mapDurationSec * 2 / 34`, `outroStart = mapDurationSec * 32 / 34`, đích là `introEnd + r * (outroStart - introEnd)`. Đồng hồ này là `mapDurationSec`, cùng đồng hồ `ambientDailyCandleIndexAt` đang dùng. File (`durationSec`) dài hơn khi MuseScore chừa đuôi tiếng; kéo theo file sẽ lệch nến dưới ngón tay. Chỉ khi bản đồ bằng 0 thì dùng độ dài file.
- Bài dài: đích là `warmupSec + r * (durationSec - warmupSec - cooldownSec)`. `durationSec` ở đây là độ dài nhạc của chương (`movement_duration`), cùng đồng hồ `spanCandleIndexAt`. Tuần `1W` có `warmupSec` và `cooldownSec` bằng 0, nên `r` phủ cả chương.

Khi chương đang nghe, `chartFocus` phóng `Sparkline` vào đoạn chương đó. Chương bên cạnh nằm ngoài khung, nên kéo playhead trên sân khấu chỉ tua trong chương đang hiện, và chỉ khi phóng đã đậu đúng chương đó. Trong lúc chart đang phóng vào, sân khấu chưa nhận kéo. Sang chương khác, hoặc đi qua nghỉ giữa chương, dùng thanh cả tác phẩm ở cụm điều khiển. Chart không zoom ra khi bắt đầu kéo.

## Nghe lại và đang phát

Công tắc nằm trên cùng cột trái, hai vế: **Nghe lại** và **Đang phát**. Đây là cách chọn loại đối tượng nghe. Nó đứng trước danh sách mã vì đổi vế là đổi cả danh sách lẫn cụm điều khiển. Cụm dưới sân khấu giữ việc chọn nhạc và vận chuyển, không kiêm thêm công tắc này.

**Nghe lại** liệt kê mã chứng khoán. Dòng mã kèm ngày phiên hoặc khung `1W`–`1Y`. Sân khấu phát file đã soạn. Cụm điều khiển có đủ năm thể loại, nhạc cụ, nghệ sĩ guitar, Nghe, Tạm dừng, Nghe lại và thanh kéo. Một mã chứng khoán không có nút đang phát, vì chưa có băng theo từng lệnh.

**Đang phát** liệt kê top 10 mã crypto. Sân khấu đi theo WebSocket. Cụm điều khiển còn bốn thể loại, Nghe và Tạm dừng. Không có Guitar, không có thanh kéo. Đoạn lịch sử khoảng 90 giây của BTCUSDT nằm trong vế này, một dòng dưới mã BTC, vì nó vẫn là băng stream chứ không phải file đã soạn. Trần 8 người nghe giữ nguyên. Khi đủ chỗ, sân khấu nói đã đủ người, danh sách mã vẫn ở lại.

Hai vế dùng chung sân khấu. Đổi vế thì đường giá và playhead nhận nguồn mới, cụm điều khiển đổi theo vế đang bật. Nghe lại gọi `recap` và `span`. Đang phát gọi `/v1/sonify/symbols` và WebSocket `/v1/sonify/ws`.

## Bốn lát

Mỗi lát dùng API đã có. Không thêm biến thể và không thêm nguồn dữ liệu. Hành vi playhead giữ nguyên. Vỏ sân khấu theo bảng màu và sóng hòa vào đường giá ở mục phong cách.

| Lát | Xong khi |
|---|---|
| A. Một bài | Hai cột. Trái: công tắc Nghe lại, rồi một mã và một ngày. Phải: sân khấu trên, cụm điều khiển dưới. Đường cyan, sóng magenta trong cùng khung, playhead amber. Nghe, dừng, nghe lại, kéo tới một phút bất kỳ |
| B. Chương | Nghe lại về đầu chương, rồi về đầu tác phẩm. Kéo playhead trên sân khấu tua trong chương đang phóng. Thanh cả tác phẩm ở cụm điều khiển sang được chương bên cạnh và qua được khoảng nghỉ. Chart không zoom ra khi kéo. `1Y` vẫn chọn được trên điện thoại |
| C. Đài | Công tắc Đang phát. Bốn thể loại, `Sparkline` và trục giá, không thanh khung `1D`–`5Y`. Mã cặp trên cột trái. Không tua |
| D. Cửa | Kệ thể loại, nhạc cụ, nghệ sĩ dẫn tới một bài replay với đủ transport |

## Sẽ làm: đèn trên sân khấu để tập tai

V1 không gắn đèn. Sân khấu vẫn là `PriceChart` và `Sparkline`, với bảng màu của phòng thu. Phần này thêm độ sáng lên đường giá và vùng tô, cùng đồng hồ với playhead. Kéo thanh thời gian hoặc bấm Nghe lại thì đèn đi theo giây đó.

Người nghe học bốn dấu, không học từng nốt. Mỗi dấu là một sự kiện đã có nghĩa trong bản nhạc. Đèn không cháy theo mọi tiếng piano hay violin.

### Bốn dấu lấy từ engine

**Giai điệu.** Violin, sax, bè hát của guitar, sáo alto của Ambient, và arpeggio synth của Tối giản (P1) đi theo giá. Playhead phát sáng nhẹ suốt lúc tiếng đó đang ngân. Đây là đèn nền. Các dấu kia chồng lên, không thay nó.

**Thanh khoản.** Bass giao hưởng đánh dày theo băng `p`–`f` trong `BASS_PATTERNS` (`render.py`): `p` là một nốt gốc giữ cả ô, `mp` là hai nốt trắng, `mf` là bốn nốt đen, `f` là chuỗi móc đơn gốc–quãng tám–quãng năm. Tối giản làm cùng việc bằng bè Pulse (`minimalist.py`): `p` thưa, `f` là móc kép và nhấn phách 2 với phách 4. Vùng tô dưới đường giá thở theo mật độ đó. `p` sáng một lần mỗi ô. `f` bước theo phách. Không nhấp theo từng cú trống.

Kèn cor đơn của Ambient là dấu thanh khoản thứ hai, không phải một đèn riêng. `French Horn` (`Horn in F`, bè P3) nở ở ô thứ hai của cửa sổ `mf` hoặc `f` trong đoạn `phrase`, cách lần nở trước ít nhất 4 ô, dài 1–2 ô (`docs/sonify-ambient.md`). Băng `f` nở tới velocity 80, băng `mf` tới 64. Vùng tô giữ sáng suốt tiếng nở, đậm hơn khi băng là `f`. `French Horns a6` của bộ Đồng giao hưởng là dàn đệm người nghe đã chọn. Dàn đó không có nghĩa khối lượng.

Trên đài live, tiếng `swell` trong `voices.py` nở khi velocity từ 82, khác cửa sổ `mf`/`f` của bản đã soạn. Đài map vai `swell` sang cùng đèn vùng tô. Không dùng chung một ngưỡng với kèn cor của bản đóng.

**Breakout.** `techniques()` trong `phrasing.py` đánh dấu nốt ngân đầu tiên trong câu vượt mọi nốt của bốn ô trước (`BREAKOUT_LOOKBACK = 32` móc đơn). Flute giao hưởng vào ở đỉnh từ Sol5 hoặc ở breakout. Vibraphone jazz nhấn breakout và đỉnh câu. Celesta của Ambient điểm đỉnh cao và breakout khi biên độ đoạn vượt 0,5%. Chuông tối giản chỉ kêu ở đỉnh và breakout. Một chấm sáng trên đỉnh giá của nến đó. Bản nhạc không có vibrato. Điểm nhấn này của jazz là vibraphone.

**Scale guitar.** `PriceImpulse` là một sóng giá có hướng, thoái lui nông, rồi phá đỉnh hoặc đáy. `guitar_scale_passages.py` tiêu ngân sách khoảng 30% thân bài để chạy scale trên sóng đó. Đoạn đường giá từ `impulse.start` tới `impulse.target` đậm lên đúng lúc scale đang chạy. Scale nội tại của điệu Bach, như móc chạy của Gigue hay nốt đi qua của Sarabande, là ngữ pháp điệu. Những nốt đó không bật đèn scale.

Tremolo của Barrios là cách hát một câu ngân, cửa theo tempo, không theo khối lượng. Humanize, echo của preset, và việc người nghe chọn bộ Dây hay bộ Đồng không phải sự kiện thị trường. Những thứ đó không có đèn.

### Dữ liệu đèn cần có

Manifest hôm nay có `peaks`, thời lượng và playhead theo nến. Không có danh sách sự kiện. Bản đã soạn cần một cue track cạnh file audio: `startSec`, `endSec`, `cue` (`melody`, `liquidity`, `breakout`, `scale`), và `band` khi dấu là thanh khoản. `render()` ghi track một lần, cùng lúc viết nốt. Client không đoán nhạc cụ từ sóng peaks, và không lưu thêm `candleStart`. Vị trí trên chart tính từ giây, bằng cùng hàm playhead.

`ambientDailyCandleIndexAt` và `spanCandleIndexAt` đang trả chỉ số nến đã làm tròn xuống. Với `1D`, một nến phút gần một móc thân bài. Với `1M` và `1Y`, vài chục nến ngày được nội suy thành nhiều ô, nên một nốt breakout vài móc nằm giữa hai nến. Khi vẽ đèn, client lấy phân số `(elapsed - đầu thân) / thân` nhân với độ dài `prices`, không làm tròn, để chấm đứng giữa hai nến. Playhead của bài hát vẫn dùng chỉ số đã làm tròn như hôm nay.

`Sparkline` nhận cue đang hoạt động từ cùng đồng hồ với `cursorIndex`. Seek và Nghe lại dịch đồng hồ đó. Đài live không có file và không có scale guitar. Vai trong payload nốt của `voices.py` map như sau:

| Dấu | Vai trên đài |
|---|---|
| Giai điệu | `violin`, `sax`, `glass`, `arp` |
| Thanh khoản | `bass`, `pulse`, `stab`, `swell`, `sub` |
| Breakout | `flute`, `vibe`, `shimmer`, `bell`, khi `allow_high` bật |

`drone`, `halo`, `pad`, `rhodes`, `piano`, `cello` và `fill` không bật đèn.

### Thứ tự khi làm

1. Khóa bốn tên cue và vị từ đúng hàm ở trên, bằng fixture một phiên giao hưởng, một phiên Ambient, và một bản guitar có `PriceImpulse`.
2. Kiểm tra nến của cue trùng ô bass, ô nở kèn, nốt breakout, và đoạn scale đã viết.
3. Sau đó mới thêm sáng lên `Sparkline`: playhead, vùng tô, một chấm, một đoạn đường. Hình sân khấu và trục giá giữ nguyên.

## Việc để sau

Những mục này có trong concept VNSoni và chưa khớp engine. V1 không làm chúng xuất hiện sớm hơn. Đèn tập tai ở mục trên đã có kế hoạch riêng. Nó vẫn đứng sau bốn lát của v1.

| Việc | Trong hệ thống hiện tại |
|---|---|
| Năm thời đại như năm thể loại duy nhất | Năm nhà là nghệ sĩ của Guitar. Visée chưa có. Bốn thể loại kia đã là cách nghe riêng. Villa-Lobos trong code là hiện đại Brazil (`sus`, Etude). Chữ Ấn tượng chỉ là nhãn nghe, không đổi dialect |
| Piano / marimba cho đài tối giản | Mallet và piano đứng thuộc bản đã đóng. Đài tối giản đang là synth trên trình duyệt. Nốt lặp được giữ |
| Cyberpunk khi giá gãy | Chưa có biến thể. Spike đổi regime và trưởng/thứ. Preset chỉ là kệ tần, echo, soft-clip nhẹ |
| Đài chứng khoán theo từng lệnh | Recap đi theo nến phút và phiên. Băng crypto đi theo aggTrade 250 ms |
| CSV, nhịp tim, thời tiết | Engine đọc `close`, `volume`, đồng hồ phiên, đấu giá, giọng nhà của mã |
| Sân khấu pan, widget, gói Pro, tài khoản | Chưa có mixer không gian, token nhúng, hay auth |
| Nền tảng sinh nhạc bằng model | Luật soạn là tất định: lượng tử hóa thang, Markov hợp âm, grammar guitar, humanize |

Tài liệu kiến trúc Musicalize viết khi v1 đã nghe được trên hai phòng.
