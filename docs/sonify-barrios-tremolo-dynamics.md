# Kế hoạch dynamics cho tremolo và intro của Barrios

> **Trạng thái**: đã render. Vòm tremolo và contour intro Barrios nằm trong code. `RECAP_REVISION` là 61, `SPAN_REVISION` là 47.

Hai chỗ phẳng:

1. Bè trầm của tremolo không đổi lực trong ô. Bè cao vẫn có nhịp ngón `a–m–i`.
2. Intro: chuông, cantabile, và bè trầm đứng một velocity. Trên 4/4, ba nốt chuông cùng một số. Bè cao của arpeggio đã đi 50–57. Cadence đã nhích sau năm nốt 56.

`_shape_dynamics` không cứu được hai chỗ này. Ô pedal bị bỏ qua. Trên ô tremolo, lực viết sẵn nhận một delta theo ô.

---

## 1. Đã nghe

Đo trên `render(..., variant="guitar", ensemble="barrios")` với form thật của từng khung. Một nốt MIDI là một velocity. Nốt nối `tie_stop` không tính lại.

### 1.1. Bè trầm tremolo

`_tremolo` (`backend/app/sonify/guitar.py`) gán mọi cú ngón cái, gốc và quãng 5, bằng `_TREMOLO_THUMB = 58`. Bè cao lặp `(52, 55, 54, 52)`. Nốt màu ở phách mạnh khi đổi hợp âm cũng lấy 58. Hai nốt của một cú ngón cái là một tiếng, nên chúng cùng lực là đúng. Điều nghe thiếu là các phách liên tiếp cũng cùng một số.

Ô phẳng vì velocity viết sẵn cộng `_BAND_DELTA` theo ô (`p` −12, `mp` −6, `mf` 0, `f` +4). Ô mẫu chương I là band `mp`: ngón cái 58 − 6 = 52, fill `46, 49, 48, 46`.

`_shape_dynamics` chỉ gọi `swell()` khi `phrase.rise > 0`. Một nốt giữ có `rise` bằng 0, nên không có extra. `_tremolo_boost` trả 0 khi `rise < 3`. Khi đỉnh nằm ở đầu câu, `swell()` bằng 1 ở onset đầu rồi giảm về 0 ở cuối câu. Nó không đứng ở 1 suốt câu.

Năm ô không phẳng trên chương I, và 17/29 ô tremolo của 1D, là các câu có `rise > 0`. `round(4 * swell())` đổi bên trong những ô đó.

Kết quả, chương I 1M (96 BPM, 4/4, selloff): 82/87 ô tremolo có bè trầm đứng yên trong ô. Qua các ô, bè trầm chỉ bước theo band, trong khoảng 46–64.

| Khung | Khi nào là tremolo | Bè trầm trong ô |
|---|---|---|
| 1M I | selloff hoặc volatile. Rally và calm là Preludio | 82/87 ô phẳng |
| 1M IV | mọi character. Pedal cuối dài nên cả thân là tremolo | 78/83 ô phẳng |
| 1W | selloff hoặc volatile. Rally và calm là Preludio | 151/151 ô phẳng |
| 3M I | selloff hoặc volatile | 179/183 ô phẳng |
| 3M III | khi macro khóa tremolo vì câu ngân, 108 BPM, 4/4 | 203/203 ô phẳng |
| 1Y tháng 100 BPM | selloff hoặc volatile | cùng kiểu |
| 1Y tháng 12 | 96 BPM, 4/4, thân tremolo | cùng kiểu |
| 1D | selloff; volatile khi hoạt động giai điệu dưới 35%; rally khi biên độ từ 1.4%. Calm là Preludio | 12/29 ô phẳng, vì nhiều câu có `rise > 0` |

1M II (72 BPM, 3/4) và 1M III (120 BPM, 6/8) không có tremolo. II là thánh ca. III là điệu.

### 1.2. Intro

`_shape_dynamics` bỏ ô `intro`, `warmup`, `outro`, `cooldown`. Lực intro là số viết trong `backend/app/sonify/guitar_frame.py`.

Chương I 1M có 8 ô pedal đầu (warmup 4 ô cộng intro 4 ô của form). `frame_roles(8)` kéo script dài thành mỗi bước hai ô:

| Ô | Cử chỉ | Bè cao | Bè trầm |
|---|---|---|---|
| 0–1 | chuông | ba nốt, cả ba đều 46 | không có nốt |
| 2–3 | cantabile | một nốt 50 suốt ô | một nốt 50 suốt ô |
| 4–5 | arpeggio đi lên | 50, 51, …, 57 | một nốt 50 |
| 6–7 | cadence | năm nốt 56, rồi 58, 60, 62 | một nốt 56. Ô cuối có thêm pickup 50 |

Chuông dùng `velocity + (cursor % 3) * 2`. `_lengths(8, 3)` ra 3, 3, 2 móc đơn, cursor 0, 3, 6, phần dư cho 3 luôn bằng 0. Trên 6/8 cursor 0, 2, 4 ra 46, 50, 48.

Cantabile và bè trầm của arpeggio là một nốt ngân hết ô. Một nốt không đổi lực giữa chừng. Bè trung cantabile cũng bốn nốt cùng 50.

Cùng helper intro của Barrios chạy ở mọi khung:

| Khung | Ô pedal đầu | Script |
|---|---|---|
| 1D | 2 | chuông, rồi arpeggio. Bè trầm ô sau giữ 50 |
| 1W | 4 | mỗi bước một ô |
| 1M I và IV, 3M 4/4 | 8 | mỗi bước hai ô, như bảng trên |
| 1Y 4/4 | 6 | warmup 2 cộng intro 4. Chuông hai ô, cantabile một ô, arpeggio hai ô, cadence một ô |
| 1M II, 1M III, 3M 3/4 và 6/8 | 10 | warmup 6 cộng intro 4. `frame_roles(10)`: chuông ba ô, cantabile hai ô, arpeggio ba ô, cadence hai ô |
| 1Y 3/4 và 6/8 | 7 | warmup 3 cộng intro 4. Chuông hai ô, cantabile hai ô, arpeggio hai ô, cadence một ô |

Intro của chương không tremolo vẫn có chuông, cantabile và bè trầm đứng yên. Contour viết trong hai hàm intro của Barrios thì phủ hết các khung này.

---

## 2. Cách sửa tremolo

Sửa vòm trong ô ở `_tremolo`. Sửa vòm vùng ở nhánh tremolo của `guitar_patterns.py`, nơi đã có `tremolo_bars`. Không mở lại `_shape_dynamics` trên các ô này. Ô `etude1` và `etude11` đã được khóa vì cùng lý do: shaping viết đè đường đã tính.

Giữ nguyên lưới. Mỗi phách một cụm bốn móc kép. Ngón cái ngân hết phách, gốc và quãng 5 cùng lúc. Hình ngón của bè cao vẫn là lệch `-6, -3, -4, -6` so với mức `L` của phách đó.

Ngón cái của một phách là `L`. Gốc, quãng 5, và nốt màu ở phách mạnh khi đổi hợp âm cùng lấy `L`. Nếu ngón cái phách đầu xuống 54 mà nốt màu giữ 58, bè trong to hơn ngón cái.

Mức gốc 58, trước khi cộng band và vòm vùng. Lệch theo phách:

| Nhịp | Các phách | Ngón cái | Fill của phách đầu |
|---|---|---|---|
| 4/4 | 4 | 54, 58, 62, 59 | phách đầu 48, 51, 50, 48. Phách beat 1.0, `L` = 58: 52, 55, 54, 52 |
| 6/8 | 3 | 54, 62, 58 | phách đầu cùng 4/4. Phách giữa, `L` = 62: 56, 59, 58, 56 |
| 3/4 | 3 | 54, 62, 58 | cùng các phách của 6/8 |

Cụm `52, 55, 54, 52` là phách có `L = 58`, tức phách thứ hai của 4/4 (beat 1.0). Phách đầu, trước band và vòm vùng, là fill `48, 51, 50, 48` với ngón cái 54.

Biên trong ô là 8. Đó là mức nhỏ nhất còn nghe trên chương dài. Bước 2 của `_tremolo_boost` hiện tại không đủ.

Vòm chậm cộng thêm trên vùng tremolo liền nhau. `t` là vị trí ô trong vùng đó, `index / (n - 1)`, từ 0 ở ô đầu tới 1 ở ô cuối. Cộng `round(6 * sin(pi * t))`. Hai đầu vùng thêm 0, ô giữa thêm 6 khi `n` lẻ. Vùng hai ô có `t` bằng 0 và 1, nên cả hai cộng 0. Muốn ô giữa lớn hơn ở phách đỉnh thì vùng phải dài ít nhất ba ô.

`guitar_patterns.py` gọi `_tremolo` với mọi ô đánh dấu `"phrase"`, rồi mới lọc `tremolo_bars`. Tính `t` trong `_tremolo` sẽ trải vòm qua cả ô Preludio bị bỏ. Vòm chậm bám tập ô tremolo thật, ở nhánh `pattern == "tremolo"` trong `guitar_patterns.py`. Lời gọi có thể truyền tập đó vào. Không suy `t` từ `kind_at` đang được truyền là toàn `"phrase"`.

Band dịch cả vòm, không xóa vòm: `p` trừ 6, `mp` trừ 3, `mf` giữ, `f` cộng 3. Kẹp ngón cái trong 44–72. Mỗi cụm, ngón cái lớn hơn nốt `m` của chính cụm đó ít nhất 3. Không đòi ngón cái phách nhẹ lớn hơn `m` của phách mạnh. Nếu đòi vậy, vòm trong ô bị bẹt.

`_shape_dynamics` bỏ qua cả ba bè của ô tremolo, giống ô etude. Nếu không bỏ, band cũ (`p` trừ 12) cộng thêm một lần nữa.

Bỏ `_tremolo_boost`. Cộng phẳng 2 hoặc 4 cho cả ô, và khóa ô đầu, là đường đang nghe. Ô đầu vùng là đầu vòm chậm. Trong ô vẫn có bốn mức.

1D dùng cùng công thức.

Không đổi cửa chọn tremolo, không đổi Preludio, choro, polca, và không viết hairpin MusicXML. Playback guitar đọc velocity từng nốt. Barrios hiện chỉ in một chữ `mp` ở ô 0.

### Test tremolo

`test_barrios_tremolo_thumb_is_strongest_and_m_leads_the_fill` gọi `_tremolo` trực tiếp, không có band và không có vòm vùng. Assert chuyển sang beat 1.0: fill `52, 55, 54, 52`, ngón cái 58, và ngón cái lớn hơn ba nốt fill của cụm đó. Bốn móc kép đầu ô là fill `48, 51, 50, 48`, ngón cái 54.

Trên bản đã render, cụm 58 chỉ đúng ở beat 1.0 của ô `mf` nằm ở đầu hoặc cuối vùng tremolo, nơi vòm chậm cộng 0. `test_phase1_held_melody_tremolo_tapers_and_breathes` bỏ `velocity == 58` cho mọi cú. Ngón cái vẫn ngân hết phách. Gốc và quãng 5 vẫn cùng beat.

`test_a_later_tremolo_bar_breathes_and_the_first_bar_stays_locked` có đúng hai ô tremolo. Hai đầu vùng đều cộng 0, nên hai ô bằng nhau ở cùng một phách. Assert vòm trong ô trên cả hai, và hai ô khớp nhau. Muốn thấy ô giữa lớn hơn 6 ở phách đỉnh thì fixture tremolo phải dài ít nhất ba ô.

Thêm một test khung dài, `1M` I selloff hoặc `1W` selloff: trong một ô tremolo giữa thân, bốn phách trầm có ít nhất hai mức, cách nhau từ 6 trở lên, và ngón cái mỗi phách vẫn cao hơn `m` của phách đó. Nốt màu ở phách đổi hợp âm bằng `L` của phách đó.

---

## 3. Cách sửa intro

Contour chỉ được lắp trong `_barrios_intro_short` và `_barrios_intro_long`.

`_cantabile` còn chạy ở outro dài của Barrios và ở intro dài của Brouwer. `_settled` còn chạy ở intro dài của Brouwer. `_scale_into` dùng chung và đang bước +2 từ velocity được truyền vào. Ba hàm đó giữ hành vi cũ khi không có tham số contour. Hai hàm intro của Barrios là nơi truyền contour, hoặc tự viết các nốt tách.

`_plant_pickup` xóa móc đơn cuối và ghi velocity 50. Assert nửa sau nhỏ hơn nửa trước so hai cú nửa ô, và để pickup ra ngoài.

Chuông không thêm bè trầm. Ô chuông cố ý chỉ có bè cao. Sửa lực các nốt theo chỉ số nốt, không theo `cursor % 3`:

| Số nốt | Velocity |
|---|---|
| 2 | 44, 50 |
| 3 | 44, 50, 46 |
| 4 | 44, 48, 52, 46 |

Cantabile phải tách nốt ngân. Nếu không tách, một velocity là trần của nốt đó. Bè cao và bè trầm được nới để bè trung còn chỗ ở giữa về velocity:

- Bè trầm hai nửa ô: 46 rồi 52.
- Bè cao hai nửa ô: 54 rồi 60.
- Bè trung bốn nốt, hai nốt mỗi nửa: 48, 50 rồi 54, 56. Nửa đầu nằm giữa 46 và 54. Nửa sau nằm giữa 52 và 60.

Arpeggio đi lên:

- Bè cao nội suy từ 46 ở móc đơn đầu tới 60 ở móc đơn cuối, kẹp 64. Trên 4/4 đó là 46, 48, 50, 52, 54, 56, 58, 60. Công thức `velocity + offset` với điểm đầu 46 dừng ở 53, không tới 60.
- Bè trầm theo phách đen, đi dưới bè cao. 4/4 bốn phách: 44, 46, 48, 50. 3/4 và 6/8 ba phách đen: 44, 47, 50.

Cadence, viết tại cadence intro của Barrios, không sửa bước +2 của `_scale_into`:

- Bè trầm hai nửa: 52 rồi 46, nhường vào thân bài.
- Nửa đầu bè cao, bốn móc trên 4/4: 54, 56, 54, 50.
- Nửa sau 4/4 là bốn móc đơn: 48, 52, 56, 60.
- Nửa sau 3/4 và 6/8 là ba móc đơn: 48, 54, 60.

### Test intro

Một test cho intro dài 4/4, form 1M chương I, bất kỳ character:

- Hai ô chuông: ba velocity 44, 50, 46, không có bè trầm.
- Hai ô cantabile: bè trầm 46 rồi 52, bè cao 54 rồi 60, bè trung 48, 50, 54, 56.
- Hai ô arpeggio: bè cao là dãy nội suy 46 tới 60, bè trầm 44, 46, 48, 50, và nốt trầm mỗi phách vẫn dưới nốt cao cùng phách.
- Ô cadence: hai cú nửa ô của bè trầm là 52 rồi 46. Pickup 50 ở móc cuối, nếu có, không tính vào hai nửa đó.

Một test outro Barrios ngắn: bè trầm và bè cao của ô harmonics cuối vẫn một mức. Một test intro Brouwer dài ở nhánh cantabile và settled vẫn một mức, để xác nhận contour không lọt sang hai caller kia.

---

## 4. Việc không làm trong lượt sửa

- Không đổi pattern nào được chọn, và không đổi tempo.
- Không sửa outro, Preludio, andante, choro, polca, vals.
- Không đổi `_cantabile`, `_settled`, và `_scale_into` khi Barrios intro không truyền contour.
- Không đưa ô pedal trở lại `_shape_dynamics`.
- Không in thêm chữ dynamics. Lực nghe được nằm ở velocity.
- Bump revision cache chỉ khi commit code render, không bump trong PR tài liệu này.
