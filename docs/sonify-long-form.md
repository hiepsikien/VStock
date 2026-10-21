# Sonify nhiều chương: 1D, 1W, 1M, 3M, 1Y

Kế hoạch form cho các bản nghe theo range chart. 5Y không làm nhạc. Trần độ dài là bản 1 năm: **12 chương, 45 phút**.

Engine hôm nay là một tiểu phẩm 30 ô nhịp, 90 BPM, dài 1:20, nén khoảng 256 nến 1 phút của một phiên HOSE. Giai điệu hát thang C major. Bộ hợp âm đang có 12 hợp âm thuận trong C major / A minor: C, F, G, Am, Dm, Em và bảy của chúng. Jazz nâng các root đó lên maj9, m9, dominant 9. Markov, phrase 8 ô, intro và coda đang khóa vào form 30 ô này.

Bản dài giữ đơn vị đó và xếp thành chương. Một chương là một đơn vị nghe trọn, có intro và coda riêng. Giữa hai chương, player nghỉ. Bên trong chương không có khoảng nghỉ đó.

Giao hưởng và jazz dùng chung số ô, chung BPM, chung chỗ nghỉ. Jazz khác ở feel, voicing và cách đánh, không khác số chương.

## Bản đồ tác phẩm

| Range | Chương | Độ dài | Hình thức chung | Giao hưởng | Jazz |
|---|---|---|---|---|---|
| 1D | 1 | 1:20 | tiểu phẩm 30 ô, 90 BPM, form hiện tại | bagatelle | một chorus ngắn |
| 1W | 1 | 7:07 | một mạch 160 ô, 90 BPM | tác phẩm một chương | một bài xuyên suốt |
| 1M | 4 | 14:42 | sonata 4 chương | nhanh, chậm, scherzo, kết | head, ballad, bài ngắn, finale |
| 3M | 3 | 24:16 | concerto / symphony vừa | nhanh, chậm, nhanh | set 1, ballad, set cuối |
| 1Y | 12 | 45:00 | tổ khúc 4 mùa | mỗi mùa: mở, chậm, khép | bốn set, mỗi set ba bài |

1M là sonata bốn phần. Hình dung tổ khúc ba chương nằm ở 3M.

Nghỉ giữa chương: 6 giây với 1M, 8 giây với 3M. 1Y nghỉ 4 giây trong một mùa và 8 giây khi sang mùa. 1D và 1W không nghỉ giữa chừng.

Đơn vị bên dưới mọi chương dài vẫn là phrase 8 ô và Markov hiện có. Intro một lần ở đầu chương, coda một lần ở cuối. Form 30 ô của 1D giữ nguyên.

## 1D

Giữ nguyên tiểu phẩm hiện tại: 2 ô intro, ba phrase 8 ô, 4 ô outro, 90 BPM. Nến 1 phút, thang giá của riêng phiên.

## 1W

Một tác phẩm, không phải năm tiểu phẩm nối nhau. Năm phiên vẫn là nến 1 phút, khoảng 8 phút thị trường mỗi ô, cùng mật độ với 1D. Mỗi phiên chiếm 32 ô và một vai:

| Phiên | Ô | Vai |
|---|---|---|
| 1 | 32 | mở |
| 2 | 32 | tương phản |
| 3 | 32 | chuyển |
| 4 | 32 | trở lại |
| 5 | 32 | kết |

160 ô ở 90 BPM là 7:07. Hết phiên giữ nốt cuối đúng một ô rồi vào phiên sau. Đó là nhịp thở trong một bài, không phải nghỉ giữa chương.

Cả tuần dùng một thang giá. Giá đóng cửa và giá mở cửa hôm sau cùng mức thì cùng một nốt. Gap qua đêm vẫn thành bước nhảy, vì giá thực sự đổi. MA20 tính trên cả chuỗi phút trước khi cắt vai, để phiên sau không bị mù ở 20 phút đầu.

Ngày đi ngang trong tuần biến động nằm trong một vùng nốt hẹp. Hòa âm vẫn theo regime của phiên đó. Cường độ p–f xếp trên volume cả tuần. Ngân sách chuông và flute vẫn theo biên độ riêng của phiên, để ngày phẳng không bị trang trí như ngày có sóng.

Thiếu phiên (nghỉ lễ) thì gộp các vai giữa. Luôn giữ đoạn mở và đoạn kết.

`render()` nhận thêm biên giá và biên volume tùy chọn. 1D không truyền gì thì giữ min/max của chính phiên.

## 1M

Bốn chương, mỗi chương một tuần. Cộng 3 lần nghỉ 6 giây là 14:42.

| Chương | Ô | BPM | Đồng hồ | Vai |
|---|---|---|---|---|
| I | 96 | 96 | 4:00 | trình bày |
| II | 72 | 72 | 4:00 | chậm |
| III | 72 | 120 | 2:24 | scherzo, ngắn và nhẹ |
| IV | 96 | 96 | 4:00 | kết, coda dài hơn chương I |

Nến 1 phút, cùng hạt với 1D và 1W. Lookback phút hiện là 18 ngày; bản tháng cần khoảng 35 ngày. Nếu API không trả đủ, chương đó dùng nến 5 phút và giai điệu mượt hơn. Tháng có 5 tuần thì tuần dư nhập vào chương IV.

Khung ô gợi ý, vẫn bội số của phrase 8 ô:

- I: 8 intro, 32 trình bày, 24 tương phản, 24 trở lại, 8 coda
- II: 8 intro, 24 câu hát, 16 đoạn giữa, 24 câu hát trở lại
- III: 8 + 16 + 16 + 16 + 8 + 8
- IV: cùng xương với I, coda 16 ô và đoạn trở lại 16 ô

## 3M

Ba chương, mỗi chương một tháng. Nến 5 phút, khoảng 6–9 nến mỗi ô. Cộng 2 lần nghỉ 8 giây là 24:16.

| Chương | Ô | BPM | Đồng hồ | Vai |
|---|---|---|---|---|
| I | 192 | 96 | 8:00 | exposition, development, recap |
| II | 120 | 60 | 8:00 | chậm, ít đổi hòa âm hơn |
| III | 216 | 108 | 8:00 | nhanh, coda |

I chia 64 + 64 + 48 + 16 ô. II là dạng aba. III dùng lại nhịp của I với coda nặng hơn.

## 1Y

Mười hai chương, mỗi chương một tháng. Nến 30 phút. Bốn mùa lặp cùng một tính cách. Tháng 12 dài hơn để kết cả năm. Cộng nghỉ (8 lần 4 giây trong mùa, 3 lần 8 giây giữa mùa) là 45 phút.

| Vị trí trong mùa | Ô | BPM | Đồng hồ | Các tháng |
|---|---|---|---|---|
| Mở | 80 | 100 | 3:12 | 1, 4, 7, 10 |
| Giữa | 72 | 66 | 4:22 | 2, 5, 8, 11 |
| Khép | 84 | 108 | 3:07 | 3, 6, 9 |
| Kết năm | 108 | 96 | 4:30 | 12 |

Tháng thưa nến vẫn là một chương; giai điệu ngân dài hơn. Mỗi chương giữ ít nhất khoảng 30 nến. Lịch sử quá ngắn thì bỏ chương trống, không kéo một giá thành cả chương.

## Thang giá và chỗ nối

1D và 1W: một thang cho cả tác phẩm. 1W bắt buộc dùng chung, vì không có nghỉ giữa chương để biện minh cho việc reset register.

1M, 3M, 1Y: một thang mỗi chương, để tuần hoặc tháng đi ngang vẫn trải được trên register. Chỗ nối nằm ở hợp âm. Chương sau chọn hợp âm mở có chung âm với nốt kết chương trước khi hai đoạn cùng vùng giá. Giá gap thì chương mới theo regime của chính nó; khoảng nghỉ là chỗ hợp lệ để đổi màu.

Chart trên app giữ độ phân giải hiện tại. Nhạc tự lấy OHLC kèm volume. Chuỗi chart đã rút xuống khoảng 90 điểm và không có volume, nên không dùng làm nguồn sonify.

Nến 15 phút, nếu sau này cần, gộp từ nến 5 phút. Nến 60 phút gộp từ nến 30 phút: volume cộng, giá lấy close cuối. Bước đầu cần xem Entrade trả `5`, `30` và `1D` đủ xa không. Resolution đã có trong code là `1`, `5`, `30`, `1D`.

Băng regime 0,15% hợp với nến phút. Trên nến 30 phút và nến ngày, sideway sẽ gần như biến mất. Nới băng theo timeframe sau khi có bản nghe 1Y.

Cờ ATO/ATC chỉ gắn trên nến 1 phút. Nến đã gộp đặt `auction` bằng false. Nghỉ trưa trong phiên vẫn bị cắt như hiện tại, và không thêm nghỉ nhạc ở 11:30.

## Mười hai hợp âm thêm

Bộ hiện tại giữ nguyên. Mười hai hợp âm dưới đây dùng chung cho mọi range, kể cả 1D. Cột jazz là voicing, cùng kiểu nâng hợp âm đang làm, không phải mười hai hợp âm thứ hai.

Giai điệu vẫn hát thang C major. Nốt lệch thang (F♯, A♭, B♭, E♭) nằm ở piano và bass. Melody chỉ bắt các âm chung với thang, nên phách mạnh không bị kéo ra khỏi C major.

| Hợp âm | Jazz | Việc của nó |
|---|---|---|
| Bm7♭5 | Bm7♭5 | bậc VII còn thiếu, thuần thang, đi qua về C hoặc Am |
| D7 | D9 | V/V, đẩy về G |
| E7 | E9 | V/vi, đẩy về Am |
| A7 | A9 | V/ii, đẩy về Dm |
| C7 | C9 | V/IV, chủ âm mang dominant, đẩy về F |
| Fm | Fm9 | bậc IV thứ mượn, màu downtrend |
| Gm | Gm9 | bậc V thứ, dominant mất cảm giác kéo lên |
| A♭ | A♭maj7 | ♭VI |
| B♭ | B♭maj7 | ♭VII |
| B♭7 | B♭9 | ♭VII7, sideway mixolydian |
| E♭ | E♭maj7 | ♭III |
| F♯°7 | F♯°7 | diminué đi qua, một ô, vào G |

Chúng không tự do trong mọi regime:

- Uptrend thêm D7 và C7 như hợp âm đi qua.
- Downtrend dùng Fm, Gm, A♭, E♭, E7, Bm7♭5.
- Sideway dùng B♭, B♭7, C7, và F♯°7 một ô trước G.

Bm7♭5 và F♯°7 không bao giờ làm chủ âm của một phrase.

MusicXML hiện từ chối nốt ngoài C major. Bước làm là cho phép các nốt đó trong bè đệm trước. Giai điệu giữ nguyên thang. Chuyển cả một chương sang giọng khác (F, B♭) là bước sau, khi các nốt lệch thang đã viết được.

## Generate

Mỗi chương là một form, nhưng xuất audio theo cụm khoảng 32 ô rồi nối sát, không chèn nghỉ. Cụm đầu mang intro, cụm cuối mang coda. 32 ô gần bằng một lần MuseScore của bản 1D, nên chương 8 phút của 3M nghe được sau cụm đầu. Các cụm sau render trong lúc phát. 1Y prefetch chương kế trong lúc chương hiện tại đang chạy.

Manifest của một span gồm nhãn chương, số nến, thời lượng, và chương nào đã có file. Khóa cache gồm mã, range, chỉ số chương, variant, số nến, và fingerprint của thang giá chương đó. Chương của ngày đang mở được render lại khi có nến mới, giống recap 1D. File 1D đã cache không dùng lại cho 1W, vì thang giá khác.

Playhead trong một chương dùng `candle_index_at` như hiện tại. Trên chart của cả range, thời gian playlist quy ra chương rồi mới quy ra nến.

## Thứ tự làm

1. Biên giá và biên volume tùy chọn trong `render()`. Manifest và player nối file. Làm 1W trước vì dữ liệu phút đã có, chỉ cần nới lookback nếu muốn đủ năm phiên sau nghỉ lễ.
2. Nghe vài mã: ngày biến động, ngày trần, tuần có gap. Chỉnh ô giữ nốt giữa hai phiên nếu một ô chưa đủ.
3. Form bốn chương của 1M, rồi ba chương của 3M, kèm gộp nến khi API không đủ phút.
4. Mười hai hợp âm, vào bè đệm trước, với cổng regime ở trên.
5. Tổ khúc 1Y và nới băng regime nếu sideway biến mất.
6. Playhead trên chart của range đang nghe.
