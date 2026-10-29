# Musicalize — kế hoạch app nghe nhạc

Web app nghe nhạc trên engine sonify và API đang có. App Expo giữ vai trò terminal cổ phiếu. Musicalize là mặt nghe mới. Tên sản phẩm là Musicalize. Module trong repo vẫn là `sonify` và `vstock`.

Tài liệu này chốt sản phẩm v1. Kiến trúc tách dịch vụ, hàng đợi MuseScore và cache audio viết sau, khi phạm vi lớn hơn hai phòng nghe.

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

## Việc để sau

Những mục này có trong concept VNSoni và chưa khớp engine. V1 không làm chúng xuất hiện sớm hơn.

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
