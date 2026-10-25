# Kế hoạch dynamics cho tremolo và intro của Barrios

> **Trạng thái**: chưa sửa code. Tài liệu này ghi điều nghe được trên Barrios MWG 1M chương I, và cách sửa.
>
> Nghe lại sau khi sửa cần bump `RECAP_REVISION` và `SPAN_REVISION` trong `backend/app/sonify/audio.py`. PR này chỉ là kế hoạch.

Hai chỗ phẳng:

1. Bè trầm của tremolo không đổi lực trong ô. Bè cao vẫn có nhịp ngón `a–m–i`.
2. Intro khóa một velocity cho cả bè cao và bè trầm. Trên 4/4, ba nốt chuông cũng cùng một số.

`_shape_dynamics` không cứu được hai chỗ này. Ô pedal bị bỏ qua. Ô tremolo của chương dài nhận cùng một offset cho mọi cú trong ô.

---

## 1. Đã nghe

Đo trên `render(..., variant="guitar", ensemble="barrios")` với form thật của từng khung. Một nốt MIDI là một velocity. Nốt nối `tie_stop` không tính lại.

### 1.1. Bè trầm tremolo

`_tremolo` (`backend/app/sonify/guitar.py`) gán mọi cú ngón cái, gốc và quãng 5, bằng `_TREMOLO_THUMB = 58`. Bè cao lặp `(52, 55, 54, 52)`. Hai nốt của một cú ngón cái là một tiếng, nên chúng cùng lực là đúng. Điều nghe thiếu là các phách liên tiếp cũng cùng một số.

`_tremolo_boost` cộng 0, 2 hoặc 4 cho cả ô, và chỉ từ ô thứ hai của câu đang lên. Ô đầu câu bị khóa. Câu tremolo thường là một nốt giữ: `phrase.apex` nằm ở đầu câu, `swell()` trả 1.0 suốt câu, nên `_shape_dynamics` cũng cộng cùng một lượng cho mọi cú.

Kết quả, chương I 1M (96 BPM, 4/4, selloff): 82/87 ô tremolo có bè trầm đứng yên trong ô. Ô mẫu là tám cú cùng 52, trong khi bè cao là `46, 49, 48, 46` mỗi phách. Qua các ô, bè trầm chỉ bước theo band thanh khoản, trong khoảng 46–64.

| Khung | Khi nào là tremolo | Bè trầm trong ô |
|---|---|---|
| 1M I | selloff hoặc volatile. Rally và calm là Preludio | 82/87 ô phẳng |
| 1M IV | mọi character. Pedal cuối dài nên cả thân là tremolo | 78/83 ô phẳng |
| 1W | selloff hoặc volatile. Rally và calm là Preludio | 151/151 ô phẳng |
| 3M I | selloff hoặc volatile | 179/183 ô phẳng |
| 3M III | khi macro khóa tremolo vì câu ngân, 108 BPM, 4/4 | 203/203 ô phẳng |
| 1Y tháng 100 BPM | selloff hoặc volatile | cùng kiểu |
| 1Y tháng 12 | 96 BPM, 4/4, thân tremolo | cùng kiểu |
| 1D | selloff; volatile khi hoạt động giai điệu dưới 35%; rally khi biên độ từ 1.4%. Calm là Preludio | 12/29 ô phẳng. Câu ngắn nên vòm câu còn lọt vào ô |

1M II (72 BPM, 3/4) và 1M III (120 BPM, 6/8) không có tremolo. II là thánh ca. III là điệu.

### 1.2. Intro

`_shape_dynamics` bỏ ô `intro`, `warmup`, `outro`, `cooldown`. Lực intro là số viết trong `backend/app/sonify/guitar_frame.py`.

Chương I 1M có 8 ô pedal đầu (warmup 4 ô cộng intro 4 ô của form). Script dài 4 bước được kéo ra:

| Ô | Cử chỉ | Bè cao | Bè trầm |
|---|---|---|---|
| 0–1 | chuông | ba nốt, cả ba đều 46 | không có nốt |
| 2–3 | cantabile | một nốt 50 suốt ô | một nốt 50 suốt ô |
| 4–5 | arpeggio đi lên | 50, 51, …, 57 | một nốt 50 |
| 6–7 | cadence | năm nốt 56, rồi 58, 60, 62 | một nốt 56. Ô cuối có thêm pickup 50 |

Chuông dùng `velocity + (cursor % 3) * 2`. Trên 4/4 ba nốt dài 3, 3, 2 móc đơn, nên cursor là 0, 3, 6. Phần dư cho 3 luôn bằng 0. Trên 6/8 cursor lệch được, nên chuông có 46, 50, 48. 4/4 thì không.

Cantabile và bè trầm của arpeggio là một nốt ngân hết ô. Một nốt không đổi lực giữa chừng. Bè trung cantabile cũng bốn nốt cùng 50.

Cùng helper chạy ở mọi khung Barrios:

| Khung | Ô intro | Script |
|---|---|---|
| 1D | 2 | chuông, rồi arpeggio. Bè trầm ô sau giữ 50 |
| 1W | 4 | mỗi bước một ô |
| 1M, 3M, 4/4 | 8 | mỗi bước hai ô, như bảng trên |
| 1Y 4/4 | 6 | chuông hai ô, cantabile một ô, arpeggio hai ô, cadence một ô |
| 1M II, 1M III, tháng 3/4 và 6/8 | 6 | cùng bốn bước, kéo trên 6 ô |

Intro của chương không tremolo vẫn phẳng. Sửa helper intro một lần là phủ hết các khung.

---

## 2. Cách sửa tremolo

Sửa trong renderer tremolo. Không mở lại `_shape_dynamics` trên các ô này. Ô `etude1` và `etude11` đã được khóa vì cùng lý do: shaping viết đè đường đã tính.

Giữ nguyên lưới. Mỗi phách một cụm bốn móc kép. Ngón cái ngân hết phách, gốc và quãng 5 cùng lúc. Hình ngón của bè cao vẫn là lệch `-6, -3, -4, -6` so với mức của phách đó. Ở mức 58, cụm đầu vẫn là `52, 55, 54, 52`.

Ngón cái của một phách là mức `L` của phách đó. Hai cao độ cùng `L`. `L` đổi theo phách, nên nghe được động lực mà không tách gốc khỏi quãng 5.

Mức gốc 58, trước khi cộng band. Lệch theo phách:

| Nhịp | Các phách | Ngón cái ở mức gốc |
|---|---|---|
| 4/4 | 4 | 54, 58, 62, 59 |
| 6/8 | 3 | 54, 62, 58 |
| 3/4 | 3 | 54, 62, 58 |

Biên trong ô là 8. Đó là mức nhỏ nhất còn nghe trên chương dài. Bước 2 của `_tremolo_boost` hiện tại không đủ.

Thêm một vòm chậm trên cả vùng tremolo liền nhau. Gọi `t` là vị trí ô trong vùng, từ 0 tới 1. Cộng `round(6 * sin(pi * t))`. Hai đầu vùng thêm 0, giữa vùng thêm 6. Vòm này không dùng `swell()` của nốt giữ, vì nốt giữ làm `swell()` bằng 1 suốt câu.

Band dịch cả vòm, không xóa vòm: `p` trừ 6, `mp` trừ 3, `mf` giữ, `f` cộng 3. Kẹp ngón cái trong 44–72. Mỗi cụm, ngón cái lớn hơn nốt `m` của chính cụm đó ít nhất 3. Không đòi ngón cái phách nhẹ lớn hơn `m` của phách mạnh. Nếu đòi vậy, vòm trong ô bị bẹt.

`_shape_dynamics` bỏ qua cả ba bè của ô tremolo, giống ô etude. Nếu không bỏ, band cũ (`p` trừ 12) cộng thêm một lần nữa.

Bỏ `_tremolo_boost`. Cộng phẳng 2 hoặc 4 cho cả ô, và khóa ô đầu, là đường đang nghe. Ô đầu của vùng tremolo là đầu vòm chậm, nhẹ hơn giữa vùng, và trong ô vẫn có bốn mức.

1D dùng cùng công thức. Không giữ ngoại lệ câu ngắn.

Không đổi cửa chọn tremolo, không đổi Preludio, choro, polca, và không viết hairpin MusicXML. Playback guitar đọc velocity từng nốt. Barrios hiện chỉ in một chữ `mp` ở ô 0.

### Test tremolo

Sửa các assert đang khóa 58:

- `test_barrios_tremolo_thumb_is_strongest_and_m_leads_the_fill`: cụm đầu vẫn `52, 55, 54, 52` khi mức phách là 58. Ngón cái phách đó lớn hơn cả ba nốt fill của cụm. Các phách sau trong ô không còn cùng một số.
- `test_phase1_held_melody_tremolo_tapers_and_breathes`: ngón cái vẫn ngân hết phách, gốc và quãng 5 vẫn cùng beat. Bỏ `velocity == 58` cho mọi cú.
- `test_a_later_tremolo_bar_breathes_and_the_first_bar_stays_locked`: ô tremolo đầu đã có vòm trong ô. Ô sau lớn hơn ở phách đỉnh vì vòm vùng, không phải vì cộng phẳng 2.

Thêm một test khung dài, `1M` I selloff hoặc `1W` selloff: trong một ô tremolo giữa thân, bốn phách trầm có ít nhất hai mức, cách nhau từ 6 trở lên, và ngón cái mỗi phách vẫn cao hơn `m` của phách đó.

---

## 3. Cách sửa intro

Chỉ bật contour ở `_barrios_intro_short` và `_barrios_intro_long`. Outro gọi cùng helper nhưng giữ mức phẳng, để cadence không mọc một crescendo mới. Pickup ô cuối intro, nếu `_plant_pickup` đã đặt, giữ nguyên.

Chuông không thêm bè trầm. Ô chuông cố ý chỉ có bè cao. Sửa lực các nốt theo chỉ số nốt, không theo `cursor % 3`:

| Số nốt | Velocity |
|---|---|
| 2 | 44, 50 |
| 3 | 44, 50, 46 |
| 4 | 44, 48, 52, 46 |

Cantabile phải tách nốt ngân. Nếu không tách, một velocity là trần của nốt đó.

- Bè trầm hai nửa ô: 46 rồi 52.
- Bè cao hai nửa ô: 48 rồi 56, cao hơn trầm.
- Bè trung, tối đa bốn nốt: 46, 50, 52, 48. Mỗi nốt nằm giữa trầm và cao đang ngân.

Arpeggio đi lên:

- Bè cao từ 46 lên 60 qua các móc đơn của ô, kẹp 64. Dốc hiện tại 50–57 quá ngắn khi bè trầm đứng yên.
- Bè trầm bốn nhịp ngắn trong ô, đi dưới bè cao: 44, 46, 48, 50. Hết một nốt 50 ngân cả ô.

Cadence:

- Bè trầm hai nửa: 52 rồi 46, nhường vào thân bài.
- Nửa đầu bè cao, bốn móc trên 4/4: 54, 56, 54, 50.
- `_scale_into` nửa sau bắt đầu từ 48 rồi bước 48, 52, 56, 60. Không còn năm nốt 56 trước khi nhích 2.

6/8 và 3/4 dùng cùng cách chia: nửa ô là một mức, bè trầm arpeggio chia theo phách đen. Không viết một dãy riêng cho từng meter nếu nửa ô và phách đã đủ.

### Test intro

Một test cho intro dài 4/4, form 1M chương I, bất kỳ character:

- Hai ô chuông: ba velocity khác nhau theo bảng ba nốt, không có bè trầm.
- Hai ô cantabile: bè cao và bè trầm mỗi bè hai mức, mức sau cao hơn mức trước.
- Hai ô arpeggio: bè cao kết thúc cao hơn ít nhất 10 so với nốt đầu, bè trầm có ít nhất ba mức và nốt trầm cuối vẫn dưới nốt cao cùng phách.
- Ô cadence: bè trầm nửa sau nhỏ hơn nửa trước.

Một test outro Barrios ngắn: bè trầm và bè cao của ô harmonics cuối vẫn một mức, để xác nhận contour không lọt sang outro.

---

## 4. Việc không làm trong lượt sửa

- Không đổi pattern nào được chọn, và không đổi tempo.
- Không sửa outro, Preludio, andante, choro, polca, vals.
- Không đưa ô pedal trở lại `_shape_dynamics`.
- Không in thêm chữ dynamics. Lực nghe được nằm ở velocity.
- Bump revision cache chỉ khi commit code render, không bump trong PR tài liệu này.
