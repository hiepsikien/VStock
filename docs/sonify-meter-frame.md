# Nhịp và khung chương

Kế hoạch bổ sung nhịp cho bốn dạng nghe, và gắn warm-up với cool-down vào từng chương từ 1M trở lên. Form, BPM và chỗ nghỉ giữa chương nằm ở `docs/sonify-long-form.md`. Khung 2 ô của bản ngày nằm ở `daily_frame.py` và `ambient.py`. 1D và 1W giữ nguyên.

Hôm nay mọi bản đều là 4/4. `BEATS_PER_BAR = 4`, mỗi ô 8 móc đơn, phách mạnh ở móc 0 và 4. Một nốt dài cả ô được viết 4 phách.

## Hai nhịp thêm cho mỗi dạng

4/4 vẫn là nhịp nhà của chương nhanh, chương kết, finale và các tháng mở hoặc khép của giao hưởng và jazz. Nhịp mới gắn vào vai, cùng một cách cho mọi mã. Đồng hồ của thân chương giữ nguyên: BPM vẫn là phách đen trong bảng form, số móc đơn của thân chương giữ nguyên, chỉ dựng lại vạch ô.

| Dạng | Thêm | Phách mạnh | Vai |
|---|---|---|---|
| Giao hưởng | 3/4, 6/8 | 3/4: phách 1. 6/8: móc đơn 0 và 3 | 3/4 cho scherzo (1M-III). 6/8 cho chương chậm (1M-II, 3M-II, tháng 2, 5, 8, 11) |
| Jazz | 3/4, 12/8 | 3/4: phách 1, hợp âm thêm ở phách 3. 12/8: móc đơn 0, 3, 6, 9 | 3/4 cho bài ngắn (1M-III). 12/8 cho ballad (1M-II, 3M-II, tháng 2, 5, 8, 11) |
| Tối giản | 5/4, 7/8 | 5/4 nhóm 3+2, nhấn móc 0 và 6. 7/8 nhóm 2+2+3, nhấn móc 0, 2 và 4 | 5/4 cho chương mở (1M-I, 3M-I, tháng 1, 4, 7, 10). 7/8 cho scherzo và chương khép nhanh (1M-III, 3M-III, tháng 3, 6, 9) |
| Ambient | 3/4, 6/4 | 3/4: phách 1. 6/4: móc đơn 0, 4 và 8 | 3/4 cho scherzo (1M-III). 6/4 cho chương chậm (1M-II, 3M-II, tháng 2, 5, 8, 11) |

Độ dài một ô, tính bằng móc đơn và bằng phách đen:

| Nhịp | Móc đơn | Phách đen | Nốt tròn cả ô |
|---|---|---|---|
| 4/4 | 8 | 4 | nốt tròn, đã có |
| 3/4 | 6 | 3 | nốt trắng chấm, đã có |
| 6/8 | 6 | 3 | nốt trắng chấm. Hai phách là móc đen chấm |
| 12/8 | 12 | 6 | nốt tròn chấm. Bốn phách là móc đen chấm |
| 5/4 | 10 | 5 | trắng buộc với đen |
| 6/4 | 12 | 6 | nốt tròn chấm |
| 7/8 | 7 | 3,5 | bảy móc đơn buộc nhau |

Jazz 3/4: bass đi mỗi phách, hợp âm ở phách 1 và phách 3, swing vẫn trên móc đơn. Jazz 12/8: bass đi bốn phách đen chấm, hợp âm ở phách 2 và 4 của bốn phách đó (móc đơn 3 và 9).

Tối giản chỉ còn backbeat phách 2 và 4 khi ô là 4/4. Ở 5/4 và 7/8, mạch móc kép giữ nguyên và nhấn chuyển sang các móc mạnh ở bảng trên. Một ô 7/8 dài 14 móc kép.

Ambient 3/4: drone ngân hết 3 phách, kính đánh phách 1. Ambient 6/4: drone ngân hết 6 phách, kính đánh phách 1. Quãng 5 của drone vẫn chỉ trên ô `mf` và `f`.

## Dựng lại ô

Một câu vẫn dài xấp xỉ 64 móc đơn, bằng câu 8 ô 4/4. Mỗi section kết thúc đúng vạch ô mới. 6/8, 3/4, 12/8 và 6/4 chia hết số móc của các chương chậm và scherzo hiện có, nên đồng hồ thân chương không đổi. 5/4 và 7/8 lệch tối đa 8 móc đơn; phần lệch chỉ rút ở coda.

Cụm xuất vẫn là ranh giới câu trong một score, cùng quy ước `docs/sonify-long-form.md`. Số ô dưới đây là thân chương, trước khi cộng khung.

### 1M

Chương I giao hưởng, jazz và ambient ở lại 96 ô 4/4, 96 BPM, 4:00. Chương IV cả bốn dạng ở lại 96 ô 4/4, 96 BPM, 4:00. Chương II của tối giản ở lại 72 ô 4/4, 72 BPM, 4:00.

| Chương | Dạng | Nhịp | Ô | BPM | Đồng hồ | Đoạn | Cụm |
|---|---|---|---|---|---|---|---|
| I | Tối giản | 5/4 | 76 | 96 | 3:58 | 8, 24, 20, 16, 8 | 32, 52, 76 |
| II | Giao hưởng | 6/8 | 96 | 72 | 4:00 | 8, 32, 24, 32 | 40, 96 |
| II | Jazz | 12/8 | 48 | 72 | 4:00 | 4, 16, 12, 16 | 20, 48 |
| II | Ambient | 6/4 | 48 | 72 | 4:00 | 4, 16, 12, 16 | 20, 48 |
| III | Giao hưởng, Ambient | 3/4 | 96 | 120 | 2:24 | 8, 24, 24, 24, 8, 8 | 56, 96 |
| III | Jazz | 3/4 | 96 | 120 | 2:24 | 8, 24, 24, 24, 8, 8 | 56, 96 |
| III | Tối giản | 7/8 | 82 | 120 | 2:23 | 8, 16, 16, 16, 14, 12 | 40, 82 |

Chương II vẫn không có outro giá. 5/4 của chương I rút 8 móc ở coda (768 xuống 760). 7/8 của chương III rút 2 móc ở coda (576 xuống 574).

### 3M

Chương I giao hưởng, jazz và ambient ở lại 192 ô 4/4, 96 BPM, 8:00. Chương II của tối giản ở lại 120 ô 4/4, 60 BPM, 8:00. Chương III giao hưởng, jazz và ambient ở lại 216 ô 4/4, 108 BPM, 8:00.

| Chương | Dạng | Nhịp | Ô | BPM | Đồng hồ | Đoạn | Cụm |
|---|---|---|---|---|---|---|---|
| I | Tối giản | 5/4 | 153 | 96 | 7:58 | 6, 45, 51, 38, 13 | 51, 102, 153 |
| II | Giao hưởng | 6/8 | 160 | 60 | 8:00 | 8, 44, 56, 44, 8 | 52, 108, 160 |
| II | Jazz | 12/8 | 80 | 60 | 8:00 | 4, 24, 24, 24, 4 | 28, 52, 80 |
| II | Ambient | 6/4 | 80 | 60 | 8:00 | 4, 24, 24, 24, 4 | 28, 52, 80 |
| III | Tối giản | 7/8 | 246 | 108 | 7:58 | 9, 64, 73, 55, 45 | 73, 146, 246 |

5/4 rút 6 móc (1536 xuống 1530). 7/8 rút 6 móc (1728 xuống 1722).

### 1Y

Tháng finale, tháng 12, cả bốn dạng ở lại 108 ô 4/4, 96 BPM, 4:30. Tháng giữa của tối giản ở lại 72 ô 4/4, 66 BPM, 4:22. Tháng khép của giao hưởng, jazz và ambient ở lại 84 ô 4/4, 108 BPM, 3:07. Tháng mở của giao hưởng, jazz và ambient ở lại 80 ô 4/4, 100 BPM, 3:12.

| Vị trí | Dạng | Nhịp | Ô | BPM | Đồng hồ | Đoạn | Cụm |
|---|---|---|---|---|---|---|---|
| Mở (1, 4, 7, 10) | Tối giản | 5/4 | 64 | 100 | 3:12 | 8, 24, 24, 8 | 32, 64 |
| Giữa (2, 5, 8, 11) | Giao hưởng | 6/8 | 96 | 66 | 4:22 | 8, 32, 24, 24, 8 | 40, 96 |
| Giữa | Jazz | 12/8 | 48 | 66 | 4:22 | 4, 16, 12, 12, 4 | 20, 48 |
| Giữa | Ambient | 6/4 | 48 | 66 | 4:22 | 4, 16, 12, 12, 4 | 20, 48 |
| Khép (3, 6, 9) | Tối giản | 7/8 | 96 | 108 | 3:07 | 8, 36, 36, 16 | 44, 96 |

Tháng mở 5/4 và tháng khép 7/8 chia hết, không rút coda.

## Meter trên FormSpec

`FormSpec` nhận một `Meter`: tử số, mẫu số, và tuple móc mạnh. 4/4 mặc định là `(4, 4)` với móc mạnh `(0, 4)`. `bars` của spec là số ô của nhịp đó. `eighths` bằng `bars * meter.eighths_per_bar`, và eighths của thân chương là đơn vị để giữ đồng hồ.

Những chỗ đang đọc hằng `BEATS_PER_BAR` và `EIGHTHS_PER_BAR` chuyển sang meter của spec đang soạn:

- `quantize_strong_beats` và `STRONG_EIGHTHS`
- walking bass và comp của jazz
- backbeat và vòng móc kép của tối giản
- quy tắc ambient: nốt dài cả ô chỉ hợp lệ khi bắt đầu ở phách 1, và độ dài đó là số phách đen của meter
- `_NOTE_TYPES` thêm nốt tròn chấm cho 6 phách. Ô 5/4 và 7/8 viết bằng nốt buộc, vì không có một loại nốt cho 5 phách hay 3,5 phách
- thẻ `<time>` trong MusicXML lấy tử số và mẫu số từ meter, viết một lần ở ô đầu

Khóa cache của chương thêm tử số và mẫu số. File 4/4 đã render không dùng cho chương đã đổi nhịp.

## Warm-up và cool-down

Từ 1M trở lên, mỗi chương có một khung ở hai đầu file của chương đó. Warm-up đứng trước intro. Cool-down đứng sau outro. Chương II của 1M không có outro giá; cool-down đứng sau câu hát cuối và là đoạn kết của chương.

Nến không trải vào khung. Nhóm nguồn của các ô khung để trống, cùng cách `assign_daily_ambient_bars` để trống ô 0–1 và 32–33 của bản ngày. Playhead đứng ở nến đầu suốt warm-up và ở nến cuối suốt cool-down. Markov, cửa sổ thanh khoản, ngân sách chuông và shimmer chỉ chạy trên thân chương.

Khoảng im lặng do player chèn giữ nguyên và đứng sau cool-down: 6 giây với 1M, 8 giây với 3M, 4 giây trong một mùa và 8 giây khi sang mùa. Người nghe hết chương bằng cool-down, nghỉ đúng số giây đó, rồi vào chương sau bằng warm-up.

### Độ dài

Khung 1M và 3M dài khoảng 16 phách đen mỗi đầu, làm tròn lên thành ô chẵn:

| Nhịp | Ô mỗi đầu | Phách đen |
|---|---|---|
| 4/4 | 4 | 16 |
| 3/4, 6/8 | 6 | 18 |
| 12/8, 6/4 | 3 | 18 |
| 5/4 | 4 | 20 |
| 7/8 | 5 | 17,5 |

1Y dùng khoảng 8 phách đen mỗi đầu, vì mười hai tháng mà mỗi tháng thêm 16 phách hai đầu sẽ kéo bản năm thêm khoảng 4 phút, qua trần 45 phút:

| Nhịp | Ô mỗi đầu | Phách đen |
|---|---|---|
| 4/4 | 2 | 8 |
| 3/4, 6/8 | 3 | 9 |
| 12/8, 6/4 | 2 | 12 |
| 5/4 | 2 | 10 |
| 7/8 | 2 | 7 |

Một ô 12/8 hoặc 6/4 đã dài 6 phách, nên nửa khung của 1Y là 2 ô (12 phách), dài hơn các nhịp kia.

Đồng hồ cả tác phẩm sau khi cộng khung, phần thân đã tính cả chỗ coda bị rút:

| Range | Giao hưởng | Jazz | Tối giản | Ambient |
|---|---|---|---|---|
| 1M | 16:10 | 16:10 | 16:08 | 16:10 |
| 3M | 25:30 | 25:30 | 25:29 | 25:30 |
| 1Y | 47:21 | 47:42 | 47:20 | 47:42 |

14:42, 24:16 và 45:00 hiện tại đã gồm khoảng nghỉ. Các mốc trên cộng thêm phần nhạc của khung vào các mốc đó. Jazz và ambient bản năm dài hơn vì tháng giữa dùng ô 6 phách, nửa khung thành 12 phách.

### Chỗ khung trong spec

`Section` thêm `warmup` và `cooldown`. Hai kind này không nhận regime, không có slot Markov, và không nằm trong `liquidity_windows_for`. Các section thân dịch sang phải đúng số ô warm-up, cùng cách thân 30 ô của bản ngày dịch sau `DAILY_WARMUP_BARS`.

Chương I giao hưởng của 1M, thân 96 ô 4/4 cộng khung 4 ô, thành 104 ô:

- warmup 0–4
- intro 4–12, phrase 12–44, phrase 44–68, phrase 68–92, outro 92–100
- cooldown 100–104

### Tiếng khung

Chủ âm warm-up là hợp âm mở của chương. Chủ âm cool-down là hợp âm kết của chương. Chương finale theo override trưởng hoặc thứ của `finale_outro` khi cả tác phẩm đổi chiều. Ô khung đạp hợp âm đó, không chạy tiến trình.

- Giao hưởng: cello và bass ngân từ phách 1. Violin vào giữa warm-up và giữ suốt cool-down. Hairpin từ `p` lên `mp` ở thân, rồi từ `mp` xuống `ppp` ở cool-down. Sáo nghỉ.
- Jazz: Rhodes đánh chủ âm ở warm-up, nốt trắng rồi nghỉ trong ô, như `_jazz_rhodes` của bản ngày. Cool-down buộc tiếp cao độ đang hát khi nốt đó chạm vạch khung. Bass buộc gốc chủ âm.
- Tối giản: khung chỉ còn mạch phách đều trên chủ âm, tenuto ở phách 1 của mỗi ô. Pad ngân và diminuendo tới `ppp`.
- Ambient: kính ngân chủ âm suốt warm-up và buộc sang câu đầu khi cùng cao độ và chạm biên. Cool-down kéo hơi đang chạm, tối đa hết khung, rồi nghỉ. Drone là pedal chủ âm.

`apply_daily_frame` vẫn chỉ nhận bản ngày 34 ô. Bản dài đi qua một lần gắn khung riêng, đọc `warmup` và `cooldown` trên spec, và dùng cùng luật buộc nốt với khung ngày: hơi cuối phrase còn cách vạch một móc đơn vẫn được nối, vì khoảng đó là hơi thở.

## Thứ tự làm

1. `Meter` trên `FormSpec`, mặc định 4/4. MusicXML viết đúng thẻ `<time>`. Bản ngày và mọi chương 4/4 nghe như hiện tại.
2. Dựng lại ô cho 3/4 và 6/8 của giao hưởng, theo bảng 1M, 3M, 1Y. Khóa cache kèm nhịp.
3. Jazz 3/4 và 12/8 trên cùng các vai. Walking bass và comp theo phách mạnh của meter.
4. Tối giản 5/4 và 7/8. Rút coda đúng số móc ở bảng. Nhấn chuyển sang móc mạnh mới.
5. Ambient 3/4 và 6/4. Drone ngân hết ô, kính vẫn vào phách 1.
6. Khung `warmup` và `cooldown` cho 1M và 3M, rồi nửa khung cho 1Y. Nến để trống trên ô khung. Playhead đứng yên ở nến biên.

## Kiểm tra

- Score 1D đủ bốn dạng giữ 4/4 và khung 2+2 hiện có.
- Một tuần đủ 5 phiên vẫn 160 ô 4/4.
- Chương III giao hưởng của 1M là 96 ô, `<beats>3</beats>`, và phách mạnh của giai điệu chỉ rơi vào phách 1.
- Số móc đơn của chương II giao hưởng 1M bằng 576, bằng thân 72 ô 4/4 cũ. Đồng hồ 4:00 ở 72 BPM.
- Chương I tối giản của 1M là 76 ô 5/4. 8 móc bị rút nằm ở coda.
- Ô `warmup` và `cooldown` không có slot Markov, không có cửa sổ thanh khoản, và nhóm nến rỗng.
- Chương II của 1M có cool-down dù spec thân không có outro.
- Cool-down cùng cao độ, chạm vạch, được buộc với nốt cuối của thân. Hairpin kết ở `ppp`.
- Khóa cache đổi khi tử số hoặc mẫu số đổi. File 4/4 của cùng chương không bị trả lại.
