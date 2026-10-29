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
- Khung `1D`, `1W`, `1M`, `3M`, `1Y`. Chương dài phóng đúng đoạn đang nghe.
- Luồng bấm Nghe, backend soạn file, playhead dùng `mapDurationSec` và `ambientDailyCandleIndexAt`.

`5Y` trên thanh khung là của chart giá, chưa có bản nhạc.

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

Máy rộng: cột trái là thể loại, nhạc cụ, nghệ sĩ và tủ bài. Mỗi dòng bài có tên, mã, ngày. Giữa là sân khấu. Máy hẹp: ba bước chọn nhạc phía trên, sân khấu ở giữa, ngày và transport ở dưới.

## Phong cách

Phòng nghe tối, cùng hệ với màn đã tinh chỉnh trong `src/theme.ts`. Nền `#000000`, mặt `#1C1C1E`, mặt nổi `#2C2C2E`, chữ trắng, chữ phụ `#8E8E93`, chữ trục `#636366`, điểm nhấn `#0A84FF`. Một màu nhấn. Thể loại không mỗi loại một màu.

Sân khấu giữ nét xanh lá `#30D158` hoặc đỏ `#FF453A` và vùng tô nhạt đang có. Hai màu đó chỉ ở trên đường giá. Chrome quanh sân khấu không dùng chúng, vì phần trăm và giá lớn đã rời màn.

Chữ lấy thang đang dùng. Tên bài là `title` (22, semibold), nằm giữa sân khấu như `PieceTitle`. Thể loại là `body` (15). Mã, ngày và số trên trục là `caption` (13), số theo `tabular-nums`. Không dùng `largeTitle` 34 và không dùng `heroPrice` 40. `player.html` đang dùng serif và vàng `#E6FF4D`. Musicalize không mang hai thứ đó sang.

Hình phẳng, không đổ bóng, không gradient, không đĩa than. Chip thể loại là pill bo tròn, nền accent khi đang chọn, chữ trắng. Chip nhạc cụ và nghệ sĩ cùng dạng pill, nền `surface` khi tắt và `surfaceElevated` khi bật. Nút Nghe bo 12, nền accent, một nút trên màn. Khoảng cách lấy `spacing` trong `theme.ts`. Chart vẫn sát mép như `PriceChart` (rộng màn trừ 8). Từ khoảng 960px, cột chọn nhạc và tủ bài ngồi hai bên sân khấu. Dưới mức đó, chúng xếp dọc.

Đèn tập tai, khi làm, chỉ đổi độ đục của playhead, vùng tô và một đoạn nét. Không thêm lớp màu mới.

## Tech stack

Mặt nghe ở trong repo này, chạy Expo web. Sân khấu, `expo-audio` và `recapCursor` đã là React Native. Một app Vite riêng sẽ phải vẽ lại `Sparkline`.

| Tầng | Chọn | Lý do |
|---|---|---|
| Web | Expo SDK 58, React Native 0.88, lệnh `npm run web` đã có | `app.config.ts` đã khai `web`. `PriceChart` dùng `react-native-svg` |
| Gói cần thêm khi làm lát A | `react-dom`, `react-native-web` | Expo web cần hai gói. Hiện chúng chỉ là peer tùy chọn trong lockfile |
| Màn | Nhóm `src/musicalize/`, ngoài `RootNavigator` của terminal | Terminal giữ watchlist, giá, tin. Entry web trỏ vào phòng nghe |
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

Trên Musicalize, Nghe lại và thanh kéo nằm cạnh nút nghe, cho cả phiên lẫn chương. Kéo playhead trên sân khấu là cùng một lệnh seek với sóng peaks. Sóng peaks giữ làm thanh thời gian, có vạch để thấy chỗ đang đứng.

Seek một phiên dùng `player.seekTo`. Playhead vẫn đi qua `ambientDailyCandleIndexAt`. Bài dài seek trong file của chương đang mở. Kéo sang vùng chương khác thì chuyển chương rồi đặt offset trong file đó. Nghỉ giữa chương tua qua được.

## Hai phòng

Cả hai phòng mở bằng thể loại và nhạc cụ.

**Replay** là tủ nhạc đã soạn, từ chứng khoán Việt Nam, khung một phiên đến một năm. Năm thể loại, đủ nhạc cụ, năm nghệ sĩ guitar. File nghe là bản MuseScore đã render. Hợp đồng sẵn: `sessions`, `recap`, `recap/audio`, `span`, `span/audio`.

**Live** là đài crypto. Bốn thể loại: Giao hưởng, Jazz, Tối giản, Ambient. Guitar và năm nghệ sĩ không có trên đài. Top 10 cặp USDT theo khối lượng 24 giờ, loại stablecoin và token đòn bẩy. Lịch sử băng chỉ BTCUSDT, khoảng 90 giây. Trần 8 socket live giữ nguyên. Hợp đồng sẵn: `/v1/sonify`, `/v1/sonify/symbols`, WebSocket `/v1/sonify/ws`.

## Bốn lát

Mỗi lát dùng API đã có. Không thêm biến thể, không thêm nguồn dữ liệu, không đổi hình sân khấu.

| Lát | Xong khi |
|---|---|
| A. Một bài | Sân khấu chạy như app. Chọn thể loại, nhạc cụ, nghệ sĩ nếu là Guitar, rồi một ngày. Nghe, dừng, nghe lại từ đầu, kéo tới một phút bất kỳ. Mã và ngày đọc được. Phần trăm và giá lớn không còn trên vỏ |
| B. Chương | Nghe lại về đầu chương, rồi về đầu tác phẩm. Kéo playhead trong chương và sang chương bên cạnh. Chart phóng đúng đoạn. `1Y` vẫn chọn được trên điện thoại |
| C. Đài | Bốn thể loại live trên cùng sân khấu. Mã cặp trên dòng đài, giá trên trục. Không tua |
| D. Cửa | Kệ thể loại, nhạc cụ, nghệ sĩ dẫn tới một bài replay với đủ transport |

## Sẽ làm: đèn trên sân khấu để tập tai

V1 không gắn đèn. Sân khấu vẫn là `PriceChart` và `Sparkline` hiện có. Phần này chỉ thêm độ sáng lên đường giá và vùng tô, cùng đồng hồ với playhead. Kéo thanh thời gian hoặc bấm Nghe lại thì đèn đi theo giây đó.

Người nghe học bốn dấu, không học từng nốt. Mỗi dấu là một sự kiện đã có nghĩa trong bản nhạc. Đèn không cháy theo mọi tiếng piano hay violin.

### Bốn dấu lấy từ engine

**Giai điệu.** Violin, sax, bè hát của guitar, và sáo alto của Ambient đi theo giá. Playhead phát sáng nhẹ suốt lúc tiếng đó đang ngân. Đây là đèn nền. Các dấu kia chồng lên, không thay nó.

**Thanh khoản.** Bass giao hưởng đánh dày theo băng `p`–`f` trong `BASS_PATTERNS` (`render.py`): `p` là một nốt gốc giữ cả ô, `mp` là hai nốt trắng, `mf` là bốn nốt đen, `f` là chuỗi móc đơn gốc–quãng tám–quãng năm. Tối giản làm cùng việc bằng bè Pulse (`minimalist.py`): `p` thưa, `f` là móc kép và nhấn phách 2 với phách 4. Vùng tô dưới đường giá thở theo mật độ đó. `p` sáng một lần mỗi ô. `f` bước theo phách. Không nhấp theo từng cú trống.

Kèn cor đơn của Ambient là dấu thanh khoản thứ hai, không phải một đèn riêng. `French Horn` (`Horn in F`, bè P3) nở ở ô thứ hai của cửa sổ `mf` hoặc `f` trong đoạn `phrase`, cách lần nở trước ít nhất 4 ô, dài 1–2 ô (`docs/sonify-ambient.md`). Băng `f` nở tới velocity 80, băng `mf` tới 64. Vùng tô giữ sáng suốt tiếng nở, đậm hơn khi băng là `f`. `French Horns a6` của bộ Đồng giao hưởng là dàn đệm người nghe đã chọn. Dàn đó không có nghĩa khối lượng.

Trên đài live, tiếng `swell` trong `voices.py` nở khi velocity từ 82, khác cửa sổ `mf`/`f` của bản đã soạn. Đài map vai `swell` sang cùng đèn vùng tô. Không dùng chung một ngưỡng với kèn cor của bản đóng.

**Breakout.** `techniques()` trong `phrasing.py` đánh dấu nốt ngân đầu tiên trong câu vượt mọi nốt của bốn ô trước (`BREAKOUT_LOOKBACK = 32` móc đơn). Flute giao hưởng vào ở đỉnh từ Sol5 hoặc ở breakout. Vibraphone jazz nhấn breakout và đỉnh câu. Celesta của Ambient điểm đỉnh cao và breakout khi biên độ đoạn vượt 0,5%. Chuông tối giản chỉ kêu ở đỉnh và breakout. Một chấm sáng trên đỉnh giá của nến đó. Bản nhạc không có vibrato. Điểm nhấn này của jazz là vibraphone.

**Scale guitar.** `PriceImpulse` là một sóng giá có hướng, thoái lui nông, rồi phá đỉnh hoặc đáy. `guitar_scale_passages.py` tiêu ngân sách khoảng 30% thân bài để chạy scale trên sóng đó. Đoạn đường giá từ `impulse.start` tới `impulse.target` đậm lên đúng lúc scale đang chạy. Scale nội tại của điệu Bach, như móc chạy của Gigue hay nốt đi qua của Sarabande, là ngữ pháp điệu. Những nốt đó không bật đèn scale.

Tremolo của Barrios là cách hát một câu ngân, cửa theo tempo, không theo khối lượng. Humanize, echo của preset, và việc người nghe chọn bộ Dây hay bộ Đồng không phải sự kiện thị trường. Những thứ đó không có đèn.

### Dữ liệu đèn cần có

Manifest hôm nay có `peaks`, thời lượng và playhead theo nến. Không có danh sách sự kiện. Bản đã soạn cần một cue track cạnh file audio: `startSec`, `endSec`, `candleStart`, `candleEnd`, `cue` (`melody`, `liquidity`, `breakout`, `scale`), và `band` khi dấu là thanh khoản. `render()` ghi track một lần, cùng lúc viết nốt. Client không đoán nhạc cụ từ sóng peaks.

`Sparkline` nhận cue đang hoạt động từ cùng đồng hồ với `cursorIndex`. Seek và Nghe lại dịch đồng hồ đó. Đài live không có file. Vai trong payload nốt (`glass`, `swell`, và các vai giai điệu) map sang ba dấu `melody`, `liquidity`, `breakout`. Đài không có scale guitar.

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
