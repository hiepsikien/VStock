# Sonify nhiều chương: 1D, 1W, 1M, 3M, 1Y

Kế hoạch form cho các bản nghe theo range chart. 5Y không làm nhạc. Trần độ dài là bản 1 năm: **12 chương, 45 phút**.

Engine hôm nay là một tiểu phẩm 30 ô nhịp. Ba biến thể trên UI không cùng tempo: giao hưởng 90 BPM (1:20), jazz 82 BPM (1:28), tối giản 118 BPM (1:01). Giai điệu hát thang C major. Bộ hợp âm đang có 12 hợp âm thuận trong C major / A minor: C, F, G, Am, Dm, Em và bảy của chúng. Jazz nâng các root đó lên maj9, m9, dominant 9 qua `JAZZ_CHORD_BY_ROOT`. Markov, phrase 8 ô, intro và coda đang khóa vào form 30 ô.

Bản dài giữ phrase 8 ô và xếp thành chương. Một chương là một đơn vị nghe trọn, có intro và coda riêng. Giữa hai chương, player nghỉ. Bên trong chương không có khoảng nghỉ đó.

Từ 1W trở đi, cả ba biến thể dùng chung số ô, chung BPM của bảng dưới, chung chỗ nghỉ. Jazz bỏ `JAZZ_BPM = 82`, tối giản bỏ `MINIMALIST_BPM = 118`. Feel nằm ở swing, voicing và mật độ nốt, không nằm ở việc chạy nhanh hay chậm hơn bảng. 1D giữ nguyên ba tempo hiện tại.

## Bản đồ tác phẩm

Đồng hồ dưới đây là BPM của form. Với 1D, cột độ dài là bản giao hưởng.

| Range | Chương | Độ dài | Hình thức chung | Giao hưởng | Jazz | Tối giản |
|---|---|---|---|---|---|---|
| 1D | 1 | 1:20 | tiểu phẩm 30 ô, form hiện tại | 90 BPM | 82 BPM, 1:28 | 118 BPM, 1:01 |
| 1W | 1 | 7:07 khi đủ 5 phiên | một mạch, 32 ô mỗi phiên, 90 BPM | tác phẩm một chương | cùng lưới, có swing | cùng lưới, thưa nốt |
| 1M | 4 | 14:42 | sonata 4 chương | nhanh, chậm, scherzo, kết | head, ballad, bài ngắn, finale | cùng vai, texture thưa |
| 3M | 3 | 24:16 | concerto / symphony vừa | nhanh, chậm, nhanh | set 1, ballad, set cuối | cùng vai, texture thưa |
| 1Y | 12 | 45:00 | tổ khúc 4 mùa | mỗi mùa: mở, chậm, khép | bốn set, mỗi set ba bài | cùng vai, texture thưa |

1M là sonata bốn phần. Hình dung tổ khúc ba chương nằm ở 3M.

Nghỉ giữa chương: 6 giây với 1M, 8 giây với 3M. 1Y nghỉ 4 giây trong một mùa và 8 giây khi sang mùa. 1D và 1W không nghỉ giữa chừng. Trong lúc nghỉ, playhead đứng yên tại điểm chart cuối của chương vừa xong.

Đơn vị bên dưới mọi chương dài vẫn là phrase 8 ô và Markov. Intro một lần ở đầu chương, coda một lần ở cuối. Form 30 ô của 1D giữ nguyên, kể cả ba tempo.

## FormSpec

`MUSICAL_BARS = 30` và `TOTAL_EIGHTHS = 240` đang khóa cứng. Bản 1W 160 ô sẽ gãy nếu các hằng này còn là kích thước của score. Bước 1 đưa một `FormSpec` vào `render()`, thay cho hằng số toàn cục:

- `bars`, `bpm`
- `sections`: danh sách `(start, end, kind)`. `kind` là intro, phrase, coda, và các vai dài hơn (trình bày, development, recap)
- cửa sổ thanh khoản suy ra từ `sections`, không dùng `LIQUIDITY_WINDOWS` của form 30 ô

Những chỗ phải đọc spec thay vì hằng số:

- `musicxml._group` đang cấp phát đúng 30 ô. Cấp phát theo `score.bars`.
- `form.plan_markov_chords` và `plan_slots` đang yêu cầu đúng 3 regime và 30 ô.
- `render`, `phrasing`, `jazz`, `minimalist` lặp `range(MUSICAL_BARS)` và pad tới `TOTAL_EIGHTHS`.
- `bell_budget` mặc định 36 móc đơn, tức 15% của 240 móc. Với chương dài, ngân sách là `round(0.15 * số móc của section)`, tính từng section trong spec. 1W tính theo từng phiên 32 ô (khoảng 38 móc), không phải 15% của cả 160 ô. `rel_span` của chuông và flute vẫn là biên độ riêng của phiên hoặc của chương, như mục thang giá.

1D truyền spec 30 ô, 3 regime, BPM theo biến thể. Hành vi nghe của 1D không đổi.

## 1D

Giữ nguyên tiểu phẩm: 2 ô intro, ba phrase 8 ô, 4 ô outro. Nến 1 phút, thang giá của riêng phiên. Giao hưởng 90 BPM, jazz 82, tối giản 118.

## 1W

Một tác phẩm, không phải năm tiểu phẩm nối nhau. Nến 1 phút. Mỗi phiên giao dịch là đúng 32 ô, tức 4 phrase 8 ô. Đủ 5 phiên thì 160 ô ở 90 BPM, dài 7:07, khoảng 8 phút thị trường mỗi ô, cùng mật độ với 1D.

| Phiên | Ô | Vai |
|---|---|---|
| 1 | 32 | mở |
| 2 | 32 | tương phản |
| 3 | 32 | chuyển |
| 4 | 32 | trở lại |
| 5 | 32 | kết |

Cụm xuất của 1W là mỗi phiên một cụm 32 ô. Mối cắt trùng ô ghim giá đóng cửa, hoặc trùng coda của phiên cuối. Tuần 3 phiên ra ba cụm, tuần 4 phiên ra bốn cụm.

Ô giữ nốt nằm trong lưới 8 ô, không phải một ô thừa bên ngoài Markov. Với các phiên trừ phiên cuối, ô 32 là ô cuối của phrase thứ 4: tám móc đơn ghim đúng giá đóng cửa. Ba mươi mốt ô trước mang nến. Markov vẫn chạy trên đủ 32 ô. Phiên cuối không có ô ghim riêng; 32 ô của phiên đó là đoạn kết, gồm coda.

Tuần thiếu phiên thì bài rút thành `số phiên × 32` ô, không kéo giãn lên 160. Phiên đầu luôn là mở, phiên cuối luôn là kết. Vai giữa bỏ bớt theo thứ tự tương phản, chuyển, trở lại. Ba phiên còn mở, chuyển, kết (96 ô, 4:16). Bốn phiên còn mở, tương phản, trở lại, kết (128 ô, 5:41). Mật độ khoảng 8 phút thị trường mỗi ô giữ nguyên.

Cả tuần dùng một thang giá. Giá đóng cửa và giá mở cửa hôm sau cùng mức thì cùng một nốt. Gap qua đêm vẫn thành bước nhảy, vì giá thực sự đổi. MA20 tính trên cả chuỗi phút trước khi cắt vai, để phiên sau không bị mù ở 20 phút đầu.

Ngày đi ngang trong tuần biến động nằm trong một vùng nốt hẹp. Hòa âm vẫn theo regime của phiên đó. Cường độ p–f xếp trên volume cả tuần. Ngân sách chuông và flute vẫn theo biên độ riêng của phiên, để ngày phẳng không bị trang trí như ngày có sóng.

`render()` nhận thêm biên giá và biên volume tùy chọn, cùng `FormSpec`. 1D không truyền biên thì giữ min/max của chính phiên.

## 1M

Bốn chương. Cộng 3 lần nghỉ 6 giây là 14:42 khi đủ bốn tuần. Cả ba biến thể dùng BPM trong bảng.

| Chương | Ô | BPM | Đồng hồ | Vai | Cụm xuất |
|---|---|---|---|---|---|
| I | 96 | 96 | 4:00 | trình bày | 40 (8+32), 24, 32 (24+8) |
| II | 72 | 72 | 4:00 | chậm | 32 (8+24), 40 (16+24) |
| III | 72 | 120 | 2:24 | scherzo | 40 (8+16+16), 32 (16+8+8) |
| IV | 96 | 96 | 4:00 | kết | 40 (8+32), 24, 32 (16+16) |

Khung ô, vẫn bội số của phrase 8 ô:

- I: 8 intro, 32 trình bày, 24 tương phản, 24 trở lại, 8 coda
- II: 8 intro, 24 câu hát, 16 đoạn giữa, 24 câu hát trở lại
- III: 8 + 16 + 16 + 16 + 8 + 8
- IV: 8 intro, 32 trình bày, 24 tương phản, 16 trở lại, 16 coda

Giọng của bốn chương. Chi tiết nằm ở `docs/sonify-sonata-mode.md`.

- Giao hưởng giữ một giọng nhà cho cả bốn chương. Tuần tăng hoặc đi ngang thì chương đó trưởng. Tuần giảm thì thứ cùng gốc. Tuần biến động chỉ sang thứ khi khúc đóng là downtrend. Intro, phách đầu câu và outro đạp bậc I của mode đó. La thứ còn đi trong câu với vai bậc vi, và không làm chủ âm của câu.
- Jazz là một set. Head, ballad và finale ở giọng nhà, mode theo tuần của chương. Ballad nghe ra ở 12/8, swing tắt và tempo chậm. Chỉ bài ngắn, chương III, bước một bậc trên vòng: tuần tăng đi lên, tuần giảm hoặc đi ngang đi xuống. Trong head, ballad và finale, đoạn giữa là bridge: phách đầu câu về bậc IV, hai ô cuối về bậc V, câu hát trở lại bậc I.
- Ambient giữ một pedal, là giọng nhà, suốt bốn chương. Mode theo tuần. Tuần tăng thì chương chậm vẫn trưởng. Scherzo chỉ đổi sang 3/4 trên cùng gốc. Đoạn giữa đổi màu hợp âm phía trên pedal, gốc không rời.
- Tối giản giữ bước giọng hiện tại: chương II và chương III sang hai giọng kế bên trên vòng, chương IV về giọng nhà.

Nến 1 phút, cùng hạt với 1D và 1W. Lookback phút hiện là 18 ngày; bản tháng cần khoảng 35 ngày. Nếu API không trả đủ, chương đó dùng nến 5 phút và giai điệu mượt hơn.

Cách chia phiên vào chương:

- Mỗi tuần lịch có phiên thì một tuần là một chương, theo thứ tự I–IV.
- Tháng có 5 tuần có phiên: tuần thứ 5 nhập cả vào chương IV, không xé ra các chương trước.
- Tuần lịch trống (Tết, cả tuần không có phiên): không để một chương rỗng và không cắt theo tuần lịch đó. Chia các phiên của tháng thành 4 khúc liên tiếp, lệch nhau nhiều nhất một phiên. Chương IV nhận phiên dư khi số phiên không chia hết cho 4.

## 3M

Ba chương, mỗi chương một tháng. Nến 5 phút, khoảng 6–9 nến mỗi ô. Cộng 2 lần nghỉ 8 giây là 24:16. Cả ba biến thể dùng BPM trong bảng.

| Chương | Ô | BPM | Đồng hồ | Vai | Cụm xuất |
|---|---|---|---|---|---|
| I | 192 | 96 | 8:00 | exposition, development, recap | 64, 64, 64 (48 recap + 16 coda) |
| II | 120 | 60 | 8:00 | chậm, aba | 40, 40, 40 |
| III | 216 | 108 | 8:00 | nhanh, coda nặng | 64, 64, 88 (48 recap + 40 coda) |

Tháng đã có khoảng ba phiên trở lên vẫn là một chương riêng; nến ít hơn thì mỗi nốt ngân lâu hơn. Tháng vừa mở, chưa đủ khoảng 150 nến 5 phút, nhập vào tháng liền trước thay vì đứng một mình thành chương III dài 8 phút. Không bỏ chương khi cả quý còn dữ liệu.

Giọng của ba chương, cùng quy tắc với bản tháng và không có bài ngắn. Giao hưởng và ambient giữ giọng nhà, mode theo tháng. Jazz cũng giữ giọng nhà cho cả ba bài. Ballad jazz vẫn có bridge sang bậc IV rồi về. Tối giản giữ bước giọng hiện tại.

## 1Y

Mười hai chương, mỗi chương một tháng, theo thứ tự thời gian của mười hai tháng gần nhất. Nến 30 phút. Form của từng chương lấy theo tháng lịch trong bảng, nên tháng 12 là finale khi nó nằm trong cửa sổ, không phải lúc nào cũng là chương cuối. Bốn mùa lặp cùng một tính cách. Cộng nghỉ (4 giây trong mùa, 8 giây khi sang mùa khác) xấp xỉ 45 phút khi đủ năm. Cả ba biến thể dùng BPM trong bảng.

| Vị trí trong mùa | Ô | BPM | Đồng hồ | Các tháng |
|---|---|---|---|---|
| Mở | 80 | 100 | 3:12 | 1, 4, 7, 10 |
| Giữa | 72 | 66 | 4:22 | 2, 5, 8, 11 |
| Khép | 84 | 108 | 3:07 | 3, 6, 9 |
| Kết năm | 108 | 96 | 4:30 | 12 |

Tháng thưa nến vẫn là một chương; giai điệu ngân dài hơn. Mỗi chương giữ ít nhất khoảng 30 nến. Lịch sử quá ngắn thì bỏ chương trống, không kéo một giá thành cả chương. Cụm xuất của 1Y bám section trong `FormSpec` của chương đó, mỗi cụm khoảng 24–48 ô và kết thúc ở cuối phrase.

## Thang giá và chỗ nối

1D và 1W: một thang cho cả tác phẩm. 1W bắt buộc dùng chung, vì không có nghỉ giữa chương để biện minh cho việc reset register.

1M, 3M, 1Y: một thang mỗi chương, để tuần hoặc tháng đi ngang vẫn trải được trên register. Chỗ nối nằm ở hợp âm. Chương sau chọn hợp âm mở có chung âm với nốt kết chương trước khi hai đoạn cùng vùng giá. Giá gap thì chương mới theo regime của chính nó; khoảng nghỉ là chỗ hợp lệ để đổi màu.

Chart trên app giữ độ phân giải hiện tại. Nhạc tự lấy OHLC kèm volume. Chuỗi chart đã rút xuống khoảng 90 điểm trong `downsample_prices` và không có volume, nên không dùng làm nguồn sonify.

Nến 15 phút, nếu sau này cần, gộp từ nến 5 phút. Nến 60 phút gộp từ nến 30 phút: volume cộng, giá lấy close cuối. Bước đầu cần xem Entrade trả `5`, `30` và `1D` đủ xa không. Resolution đã có trong code là `1`, `5`, `30`, `1D`.

Băng regime 0,15% hợp với nến phút. Trên nến 30 phút và nến ngày, sideway sẽ gần như biến mất. Nới băng theo timeframe sau khi có bản nghe 1Y.

Cờ ATO/ATC chỉ gắn trên nến 1 phút. Nến đã gộp đặt `auction` bằng false. Nghỉ trưa trong phiên vẫn bị cắt như hiện tại, và không thêm nghỉ nhạc ở 11:30.

## Mười hai hợp âm thêm

Bộ hiện tại giữ nguyên. Mười hai hợp âm dưới đây dùng chung cho mọi range, kể cả 1D, và cho cả ba biến thể. Cột jazz là voicing ghi trên chính `Chord`, không phải mười hai hợp âm thứ hai.

Giai điệu vẫn hát thang C major. Nốt lệch thang (F♯, A♭, B♭, E♭, và C♯, G♯ khi hợp âm có các âm đó) nằm ở piano và bass. Melody chỉ bắt các âm chung với thang, nên phách mạnh không bị kéo ra khỏi C major và `quantize_strong_beats` giữ nguyên.

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

### Khi đưa vào code

`JAZZ_CHORD_BY_ROOT` đang khóa theo `root_step`. Thêm `C7` cạnh `C`, `Fm` cạnh `F`, `F♯°7` cạnh `F` thì một chữ cái không còn đủ. Mỗi `Chord` có trường `jazz_voicing`. `jazz_chord()` đọc trường đó.

`same_root` trong `plan_markov_chords` đang so mỗi `root_step`. Đổi thành cùng `(root_step, alter, quality_group)`. Nhóm chất: major, minor, dominant, half-diminished, diminished. `C` và `C7` khác nhóm. `F` và `Fm` khác nhóm. `B♭` và `B♭7` khác nhóm. `prob * 2.0` đang giả định mỗi root có đúng hai hợp âm (hợp âm ba và hợp âm bảy). Bỏ cách nhân đó. Xác suất chuyển root lấy thẳng từ bảng root-to-root, rồi chia đều cho các chất đang được phép của root đích.

`midi_to_pitch` hôm nay chỉ viết nốt thuận của C major, và `midi % 12 == 8` không phân biệt được G♯ với A♭. Chính tả lấy từ hợp âm của ô đó: E7 viết G♯, Fm và A♭ viết A♭, D7 và F♯°7 viết F♯, A7 viết C♯. Thẻ `<pitch>` có `<alter>` khi nốt lệch.

`_harmony` hôm nay chỉ xuất `<root-step>`. A♭, B♭, E♭, F♯°7 cần `<root-step>` là chữ cái và `<root-alter>` là `-1` hoặc `1`. Không nhét ký hiệu giáng vào `<root-step>`.

Bè bass đang lấy quãng 5 đúng bằng `root + 7` trong `render.py` (`FIFTH = 7`) và trong walking bass của `jazz.py`. Bm7♭5 và F♯°7 có quãng 5 giảm, tức +6. Cộng cứng +7 sẽ đặt F♯ dưới Bm7♭5 và C♯ dưới F♯°7. Bậc 5 lấy từ `chord.pitches[2]`, cùng cách `voices.py` và `minimalist.py` đã lấy `fifth_pc`. Quy tắc flute chỉ chồng quãng 3 và quãng 5 đúng trên giai điệu giữ nguyên, vì giai điệu không hát âm 5 giảm.

MusicXML hiện từ chối nốt ngoài C major. Bước làm là cho phép các nốt đó trong bè đệm, với chính tả ở trên. Giai điệu giữ nguyên thang. Chuyển cả một chương sang giọng khác (F, B♭) là bước sau, khi các nốt lệch thang đã viết được.

## Generate

File mà client phát là một file cho mỗi chương. Nghỉ 4, 6 hoặc 8 giây chỉ nằm giữa chương, do player chèn. Client không nối file ở giữa một chương.

`Score` của cả chương được dựng trước: Markov, phrasing, và dovetail flute, violin, cello chạy trên đủ số ô. MuseScore mở một lần và xuất cả chương đó. Cột «cụm xuất» trong các bảng form vẫn mô tả ranh giới câu bên trong score; chúng không còn thành từng lần gọi MuseScore, vì mỗi lần gọi trên macOS mở rồi đóng app.

Đuôi reverb nằm ở cuối chương, cùng quy ước `map_duration` của bản 1D. Không cắt đuôi giữa chương, vì bản nhạc được render liền.

Manifest của một span gồm nhãn chương, số nến, thời lượng, chương nào đã có file, và mảng `prices` đúng nến đã dùng để soạn chương đó. Khi đang nghe, chart bỏ chuỗi history đã downsample và vẽ các nến này. Chương đang phát chiếm khoảng 70% chiều ngang. 30% còn lại là đoạn mở của chương kế, cùng đơn vị nến. Sang chương sau thì cửa sổ trượt: chương mới đầy 70%, chương kế tiếp chiếm 30%. Chương cuối chiếm cả khung. Trong lúc nghỉ, playhead đứng ở nến cuối của chương vừa xong.

Khóa cache gồm mã, range, chỉ số chương, variant, số nến, và fingerprint của thang giá chương đó. Chương của ngày đang mở được render lại khi có nến mới, giống recap 1D. File 1D đã cache không dùng lại cho 1W, vì thang giá khác.

Playhead trong một chương dùng `candle_index_at` trên nến của chương đó, trong phần 70% đang hiện. Thời gian playlist quy ra chương, trừ các khoảng nghỉ, rồi mới quy ra nến.

## Thứ tự làm

1. `FormSpec` và biên giá, biên volume tùy chọn trong `render()`. Các vòng 30 ô đọc spec. Manifest và player nối chương, với nghỉ giữa chương. Làm 1W trước vì dữ liệu phút đã có. Tuần thiếu phiên rút theo `số phiên × 32`.
2. Dựng `Score` cả chương và xuất một file WAV bằng một lần MuseScore. Một M4A mỗi chương.
3. Nghe vài mã: ngày biến động, ngày trần, tuần có gap, tuần 3 phiên. Nghe ô 32 ghim giá đóng cửa.
4. Form bốn chương của 1M, rồi ba chương của 3M, kèm gộp nến khi API không đủ phút. Tháng thiếu tuần chia theo quy tắc phiên ở mục 1M.
5. Mười hai hợp âm: `jazz_voicing`, `same_root` theo nhóm chất, `<root-alter>`, chính tả thăng giáng theo hợp âm của ô, bậc 5 lấy từ `chord.pitches[2]`. Vào bè đệm trước, với cổng regime ở trên.
6. Tổ khúc 1Y và nới băng regime nếu sideway biến mất.
7. Lúc nghe, chart vẽ nến sonify của chương hiện tại (khoảng 70%) và đoạn mở chương sau (khoảng 30%). Playhead đứng yên suốt khoảng nghỉ.
