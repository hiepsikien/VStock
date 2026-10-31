# Pattern, texture, và cửa intro/outro của Torroba

> **Trạng thái**: đã sửa theo phản hồi. Lưới móc của ba pattern mới nằm ở mục 3. Chưa có trong code.
> **Khung đang chạy**: [`docs/sonify-guitar-frame-variations.md`](./sonify-guitar-frame-variations.md) mục 4. Bốn pattern và tám texture: [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md), [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md). Tên in: [`docs/sonify-pattern-names.md`](./sonify-pattern-names.md).
> **Nguồn đã đọc**: *Simancas* (tab E. Ceja), *Zafra* (bản classclef, Allegretto vivace, nốt đen = 110), *Redaba* (bản Cadencia 1973, Allegretto, 3/4, Mi trưởng, 54 ô), *Alcañiz* (bản Segovia, tab ohdan, Allegro, móc đơn = 168, 3/8, La trưởng), *Olite* (bản Cadencia, phụ đề *Fiesta del Rey Noble*, Vivace, nốt đen = 95, 2/4, La trưởng, 109 ô). *Suite Castellana* đã có Fandanguillo, Danza, Arada và Float.

Mục 1 khóa pattern, texture và cửa. Mục 2 là một bảng mood. Mục 3 là hợp đồng giá và lưới móc của Juglar, Alcaniz, Olite. Mục 4 là cửa của bốn pattern đang hát và của ba pattern mới.

---

## 1. Pattern và texture

**Pattern** là đơn vị scheduler khóa cho một vùng hình thức, và là tên in trên dòng chương. Một câu thuộc một pattern. Pattern có một thói quen tay phải đủ để hát cả vùng đó, một cửa intro, và một cửa outro.

Bốn pattern đang hát:

| Id | Tên in | Thói quen tay phải |
|---|---|---|
| `castillo` | Castillo | Một nốt giá ngân, bass buông. Chậm thì Arada và Float xen vào |
| `sonatina` | Sonatina | Rải và đối thoại của *Sonatina* I |
| `fandanguillo` | Fandanguillo | Điệu 3/4–6/8, quạt ở ô đầu câu |
| `danza` | Danza | Hợp âm staccato đầu nhóm ba. Scherzo `calm`, thân bài 3/4 và 6/8. Bounce vẫn là texture của Danza. Danza không nhận vai điệu nhanh của 4/4 |

**Texture** là cách đánh bên trong pattern đã khóa. Tám texture đang hát: Arpeggio, Rasgueado, Pizzicato, Dialogue, Arch, Bounce, Arada, Float. Mỗi texture thuộc một pattern cha, theo bảng ở [`docs/sonify-pattern-names.md`](./sonify-pattern-names.md) mục 3. Texture không có id trong `_FAMILY`, không vào `_PATTERN_TITLE`, không lên dòng chương. Ô pedal không nhận texture, vì ô pedal không có đường giá.

Một câu giữ một texture. Tám texture đang hát giữ bước 7 của mục 4.0 trong kế hoạch câu: câu `n` lẻ là lưới nền, hai câu sát nhau không lặp cùng một số texture. Ba pattern mới dùng thứ tự ở đầu mục 3. Câu `closes` luôn thưa. Cửa “đừng lặp câu thưa” chỉ áp cho câu `rise < 3` chưa đóng.

**Cửa** là kịch bản intro và outro của pattern. Cửa đọc hợp âm chức năng, không đọc `_melody_at`. Cửa không phải texture.

Dòng chương in pattern. Chương một pattern in một tên, ví dụ `Sonatina (4/4, 96 BPM)`. Chương đi A–B–A in cả hàng, ví dụ `Castillo — Sonatina — Castillo`. Texture không thêm chữ vào hàng đó.

---

## 2. Form các chương không phải 1D

Form giữ như các nhà kia, và như mục 7 của [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md). `bridge` và `trio` đang có trong `span.py` là hai vùng giữa. Không thêm hình A–BCB–A.

`_assign_macro` trong `guitar_patterns.py` đã làm đúng việc này với Torroba:

- **1D** (34 ô, 4/4, không trio, không bridge): cả thân một pattern, theo bảng mood 4/4. Texture xoay bên trong pattern đó. 1D đứng ngoài A–B–A.
- **1W một phiên** (32 ô, không contrast): cả thân một pattern, cùng cửa `bars <= 40`.
- **Chương có bridge hoặc trio**: A–B–A. A là `_torroba_primary`. B là `_torroba_contrast`. A trở lại. Pedal không đổi pattern.

Guitar lấy form symphony rồi đổi nhịp: chương chậm thành 3/4, scherzo thành 6/8. Chỗ contrast đang gắn:

| Chương | Vùng giữa | A–B–A của Torroba hôm nay |
|---|---|---|
| 1M II, 3M II, chương giữa của 1Y | `bridge`, 3/4, BPM ≤ 72 | Castillo — Sonatina — Castillo |
| 1M III, scherzo của 1Y | `trio`, 6/8 | A là Danza hoặc Fandanguillo theo mood. B là Castillo khi A là điệu. A đã là Castillo thì B là Sonatina |
| 1M I, 1M IV, 3M I, 3M III, tháng mở và tháng cuối của 1Y | không gắn bridge, không gắn trio | Mỗi slot chọn một pattern theo mood của slot đó, cùng Sor, Villa và Brouwer. Slot đầu và slot cuối trùng pattern khi mood trùng |
| 1W nhiều phiên | không contrast, dài hơn 40 ô | Mỗi phiên một pattern theo mood của phiên |

Bach và Barrios, khi bài dài hơn 40 ô, đi một hàng palette trước trio. Torroba không mở hàng đó.

Bảng trên là code đang chạy. Bảng dưới là đề xuất. 1D, 1W và chương 4/4 không có bridge không có vùng B: mỗi khung một pattern theo mood. Chương có bridge hoặc trio mới có cột B.

| Khung | Mood | A | B |
|---|---|---|---|
| 4/4, kể cả 1D và 1W | `calm` | Castillo | — |
| 4/4 | `rally` | Sonatina | — |
| 4/4 | `selloff` | Sonatina | — |
| 4/4 | `volatile` | Olite | — |
| 3/4, BPM ≤ 72, có bridge | `calm` của đoạn giữa | Castillo | Juglar |
| 3/4, BPM ≤ 72, có bridge | `rally`, `selloff`, `volatile` của đoạn giữa | Castillo | Sonatina |
| Scherzo 6/8, có trio | `calm` | Danza | Castillo |
| Scherzo 6/8 | `rally` | Alcaniz | Castillo |
| Scherzo 6/8 | `volatile` | Fandanguillo | Castillo |
| Scherzo 6/8 | `selloff` | Castillo | Sonatina |

Mood của đoạn giữa đọc trên các câu của vùng B, cùng cách `_dominant_pattern` đọc một nhóm câu. `rally` và `selloff` của 4/4 vẫn cùng Sonatina. Hướng của giá trên 4/4 nằm ở texture sẵn có của Sonatina. `rally` và `volatile` của scherzo tách thành Alcaniz và Fandanguillo.

---

## 3. Ba pattern mới

Nốt hát là `_melody_at`. Nốt trên của hợp âm là `_melody_at` của móc đó. Fret trong tab là hình: slur, song thanh, hợp âm hay nốt đơn. Bass buông giữ khi `_torroba_bass` trả dây Mi, La hoặc Rê. Harmonic vận tốc 48 chỉ khi cao độ vang trùng nút và nốt dài ít nhất hai phách, cửa đang có. Nốt còn lại là nốt hợp âm hoặc nốt thang.

`phrase.rise` và `closes` chọn mật độ. `MIN_RISE` là 3, cùng cửa vòm của Fandanguillo. Thứ tự một câu:

1. Câu `closes` hát lưới thưa. Cửa sát nhau không đụng câu này.
2. Câu `rise < 3` và chưa đóng hát lưới thưa, trừ khi câu liền trước cũng thưa vì `rise < 3`. Câu đó hát hình nốt của lưới nền, không accent, không sàn 68.
3. Câu `rise >= 3` và chưa đóng hát lưới nền, với accent và sàn của pattern đó.

Juglar và Olite không có texture dày nào khác lưới nền. Alcaniz chỉ có texture mở đầu ở câu `n = 0`, hai ô đầu. Mọi câu `n` chẵn còn lại của Alcaniz hát lưới nền. Không thêm một kiểu nữa để lấp các câu chẵn.

Ô điệu dùng một `extra` cho cả ô, cùng anchor của `danza` và `fandanguillo`, để khoảng đã viết sống sót qua `apply_guitar_wave`. Phách mạnh của ô điệu viết `max(_note_velocity, 68)` và `accent=True`. Profile sóng của ô điệu cùng hàng `danza`: snap 68/70, một nốt móng mỗi câu, ba nốt mỗi đoạn, target `accent`. Ô thưa và ô tremolo không lấy sàn 68.

Cửa intro/outro của ba pattern này nằm ở mục 4.5, 4.6 và 4.7. Cửa hát bậc của hợp âm chức năng, không hát bộ ba tremolo và không hát nét chạy của thân bài.

### 3.1 Juglar — id `torroba_tremolo`

Chữ **Tremolo** trên chart thuộc Barrios. Tên in là **Juglar**. Id `tremolo` và hàng bốn móc kép của Barrios giữ cho Barrios.

Lưới nền là tremolo của *Simancas*: từ ô 5 của tab, giai điệu lặp một nốt, bass đúng đầu phách. Một phách của engine là hai móc đơn. Ba cú không rơi lên lưới móc đơn. Chúng là bộ ba móc đơn trong thời gian của một phách, tỉ lệ 3:2. `divisions = 12` đã có vì quạt: một phách là 12 tick, ba cú ở tick 0, 4 và 8. Onset `1/12` và `2/12` của quạt không dùng cho tremolo. Juglar chỉ hát trên 3/4 của chương chậm. Ô 3/4 có ba phách, mở ở móc 0, móc 2 và móc 4. Chỉ móc 0 là phách mạnh của meter.

Cả bộ ba của một phách lấy một cao độ: `_melody_at` của móc chẵn mở phách đó. Móc lẻ không đổi nốt giữa chừng bộ ba.

| Cú | Tick trong phách | Vai |
|---|---|---|
| 1 | 0 | Lead là `_melody_at` của móc mở phách. Bass `_torroba_bass` chỉ ở cú này. Accent và lớp móng chỉ khi phách mở bằng móc 0 và câu đang hát lưới nền đầy. Vận tốc là `_note_velocity`, không sàn 68 |
| 2 | 4 | Cùng cao độ. Không accent. Viết thấp hơn cú 1 đúng một bậc `_under_lead` |
| 3 | 8 | Cùng cao độ. Không accent. Cùng bậc cú 2. Bass nghỉ |

Phách mở ở móc 2 và móc 4 vẫn đủ ba cú, cùng bảng, không accent, không sàn 68. Bè trong nghỉ suốt bộ ba. Profile sóng cùng hàng `sonatina`: snap 66/68, một nốt mỗi câu, hai nốt mỗi đoạn. Ô tremolo lấy một `extra` cho cả ô, để bậc giữa cú 1 và hai cú sau sống sót qua sóng.

Lưới thưa, theo thứ tự đầu mục 3: chỉ cú 1 của mỗi phách, trường độ hết phách (`duration_beats = 1.0`). Cú 2 và cú 3 nghỉ. Không accent. Câu bị đẩy về hình lưới nền vì cửa sát nhau vẫn đủ ba cú, và cũng không accent.

Chỗ trong bảng mục 2: B của chương chậm khi đoạn giữa là `calm`. A là Castillo. Dòng chương là `Castillo — Juglar — Castillo`. Đoạn giữa `rally`, `selloff` hoặc `volatile` giữ B là Sonatina. *Zafra* là Allegretto vivace, nốt đen = 110. *Redaba* là Allegretto. Hai điệu đó không hát ở BPM ≤ 72. PDF của *Redaba* chưa đủ nốt để chốt lưới móc. Hai điệu chưa vào `_FIGURES` và chưa có ô trong bảng mood.

### 3.2 Alcaniz — id `alcaniz`, tên in **Alcaniz**

*Alcañiz (Festiva)*, bản Segovia. Allegro, móc đơn = 168, nhịp 3/8, giọng La trưởng. Engine không có nhịp 3/8. Scherzo 6/8 có phách mạnh ở móc 0 và móc 3, đúng hai đầu nhóm 3/8. Chương 3/4 chỉ móc 0 là phách mạnh. Alcaniz không gán vào chương 3/4.

*Festiva* là Allegro. Scherzo `calm` giữ Danza, điệu biên hẹp đang hát. Alcaniz nhận scherzo `rally`, chỗ giá chạy. B là Castillo vì A là điệu. Dòng chương là `Alcaniz — Castillo — Alcaniz`.

Lưới nền là điệu. Trong mỗi nhóm ba móc, đầu nhóm là giai điệu, móc kế là bass đáp.

| Móc 6/8 | Vai |
|---|---|
| 0 và 3 | Lead `_melody_at`, `accent=True`, `max(_note_velocity, 68)`. Hai móc này là hai phách mạnh |
| 1 và 4 | Bass một móc đơn, `_torroba_bass` khi hợp âm có bass buông. Không accent |
| 2 và 5 | Nghỉ |

Trong một nhóm, đầu nhóm mạnh hơn móc đáp. Cả hai đầu nhóm đều là phách mạnh của 6/8, nên cả hai lấy sàn 68.

Texture mở đầu chỉ câu `n = 0` của vùng, khi `rise >= 3` và câu chưa `closes`, trên hai ô đầu. Các ô sau của câu là lưới điệu.

| Móc 6/8 | Vai |
|---|---|
| 0 | Hợp âm, nốt trên là `_melody_at`, accent, sàn 68. Bass buông khi `_torroba_bass` trả dây buông |
| 1, 2 | Hai nốt lead slur, bước thang vào `_melody_at` của móc 3. Hình pull-off là slur, không chép fret |
| 3 | Lead `_melody_at`, accent, sàn 68 |
| 4, 5 | Bè trong đi song thanh quãng 3 hoặc quãng 6 dưới lead, nốt hợp âm hoặc nốt thang. Lead hát `_melody_at` của móc đó |

Texture mềm là lưới thưa, theo thứ tự đầu mục 3. Đây là đoạn sau ending 2 của bản: nốt dài, slur, pedal. Câu bị đẩy về hình điệu vì cửa sát nhau giữ các móc của bảng điệu, bỏ accent và bỏ sàn 68.

| Móc 6/8 | Vai |
|---|---|
| 0 | Lead `_melody_at`, `duration_beats = 1.5`, phủ móc 0–2. Không accent, không sàn 68. Vận tốc là `_note_velocity` |
| 3 | Cùng hình, phủ móc 3–5 |
| 1, 2, 4, 5 | Nghỉ |
| Bass | Một nốt ở móc 0, `_torroba_bass` khi có dây buông, trường độ một móc đơn |

Ô mềm dùng profile `castillo`: không snap. Ô điệu và hai ô mở đầu dùng profile hàng `danza`. Ô harmonic cuối của coda chỉ ra vận tốc 48 khi cửa harmonic đang có khớp. Đoạn móc ba mươi hai của bản là nét nối, cùng vai nét chạy ngắn đã có, không thành texture.

### 3.3 Olite — id `olite`, tên in **Olite**

*Olite*, phụ đề *Fiesta del Rey Noble*. Vivace, nốt đen = 95, nhịp 2/4, giọng La trưởng, 109 ô. Thân Vivace đến khoảng ô 63, *Tempo 1* từ ô 90. Ô 69–89 là Lento, nốt đen = 60.

Olite là pattern. Fandanguillo là điệu 3/4–6/8. Danza là điệu nhóm ba của scherzo `calm`. Olite là điệu đôi, nhận `volatile` của mọi chương 4/4, kể cả 1D. `calm` 4/4 vẫn là Castillo. `rally` và `selloff` 4/4 vẫn là Sonatina. Fandanguillo giữ scherzo `volatile`.

Engine không có nhịp 2/4. Hai ô 2/4 thành một ô 4/4. Hợp âm rơi vào móc 0 và móc 4, hai phách mạnh. Nét bảy nốt trên bản (`5-5-4-2-3-2-0`) không nằm trong một phách và không chia hết cho tám móc. Nốt giá ở móc 0 và móc 4 giữ nguyên: đó là `_melody_at` của chính móc đó.

Mỗi nhóm móc yếu đi về nốt giá kế. Nhóm móc 1, 2, 3 đi về `_melody_at` của móc 4. Nhóm móc 5, 6, 7 đi về `_melody_at` của móc 0 ô sau. Trong một nhóm:

- Giá đứng yên: cả nhóm nghỉ.
- Số bậc thang nhỏ hơn số móc của nhóm: đi từng bậc, rồi lặp nốt vừa tới cho hết nhóm.
- Số bậc thang lớn hơn số móc: các móc đầu đi từng bậc, móc cuối của nhóm nhảy một lần tới nốt giá kế.

Lưới nền, câu `rise >= 3` và chưa `closes`, và câu bị đẩy về hình này vì cửa sát nhau. Câu bị đẩy bỏ accent và bỏ sàn 68. Câu lưới nền đầy giữ cả hai.

| Móc 4/4 | Vai |
|---|---|
| 0 | Hợp âm, nốt trên `_melody_at`. Accent và sàn 68 khi câu là lưới nền đầy. Bass buông khi `_torroba_bass` trả dây buông |
| 1, 2, 3 | Lead đơn theo luật nhóm ở trên, hoặc nghỉ. Không hợp âm |
| 4 | Hợp âm, nốt trên `_melody_at` của móc 4. Accent và sàn 68 khi câu là lưới nền đầy |
| 5, 6, 7 | Lead đơn theo luật nhóm ở trên, hoặc nghỉ |

Profile sóng của câu đầy cùng hàng `danza`. Một `extra` cho cả ô. Câu bị đẩy dùng profile `castillo`, không snap.

Texture thưa lấy từ Lento, theo thứ tự đầu mục 3. 1D không có vùng B. Câu `closes` luôn thưa, nên ngày `volatile` vẫn có câu đổi mật độ.

| Móc 4/4 | Vai |
|---|---|
| 0 và 4 | Một nốt lead `_melody_at`. Không hợp âm, không sàn 68, không accent |
| 1, 2, 3, 5, 6, 7 | Nghỉ |
| Bass | Một nốt ở móc 0 |

Ô thưa dùng profile `castillo`, không snap.

---

## 4. Cửa theo pattern

Bảy pattern có kịch bản cửa ở dưới. Hôm nay bốn id đang hát vẫn đi `torroba_frame`: `calm` và `rally` hát một nốt giá trên bass buông, `volatile` và `selloff` đánh một hợp âm khối ở móc 0, ô outro cuối giọng thứ là Picardy. Ba id mới chưa có trong code.

`render_intro` / `render_outro` rẽ theo `(ensemble, pattern)` khi pattern có cửa trong `DOORS`. Bốn id chưa có cửa, nên mọi chương đi `_torroba` trong `guitar_frame.py`.

Mỗi pattern có một kịch bản ngắn (bước 0–1) và một kịch bản dài (bước 0–3). `frame_roles` và `_compressed` giữ nguyên. Bản 1 ô vẫn cắt đôi bản ngắn.

Cửa đọc pattern, không đọc mood. Picardy chỉ còn ở outro của `castillo`. Fandanguillo, Danza, Alcaniz và Olite khép bằng hợp âm của điệu. Juglar khép bằng một nốt ngân.

Cửa hát hợp âm chức năng `I`, `iv`/`IV`, `V7` qua `_function`, cùng cách cửa Bach và Sor. Giọng thứ giữ bậc 3 thứ, trừ ô outro cuối của `castillo`.

Bước nào `frame_roles` lặp thì ô giống hệt. `_compressed` giữ nửa đầu bước 0 và dựng bước 1 vào nửa sau. Nửa sau vẫn mở bằng đúng nhịp của pattern, để bản 1 ô không mất phách đó. Nốt dẫn chỉ thuộc ô intro cuối, và nằm sau nhịp ấy: Juglar từ móc 5, Alcaniz là cao độ của lead móc 3, Olite ở móc 6 và móc 7. `_scale_into` ghi mỗi nốt dài một móc đơn. Juglar và Olite để trống đúng các móc đó, nên gọi hàm khớp. Alcaniz chỉ lấy cao độ của một nốt từ hàm, rồi ngân nốt ấy `duration_beats = 1.5`. Gọi nguyên hàm sẽ cắt nhóm sau thành một móc đơn ngay trên ô chạm thân bài.

Profile ô pedal của cả bảy cửa là `"torroba"`. `_PEDAL_DOOR_PROFILE` đã có bốn khóa đang hát. Ba khóa `torroba_tremolo`, `alcaniz` và `olite` thêm cùng profile đó, cùng trần bass 53. Cửa bè trung trên 65, khi còn dưới bè cao, giữ nguyên. Ô pedal không đi qua `_plant_pickup`.

Vận tốc viết theo bậc thang của [`docs/sonify-guitar-frame-variations.md`](./sonify-guitar-frame-variations.md) mục 4.2. Lưới chung: intro bước 0 ở `_PP` (46), bước 1 ở `_P` (50), bước 2 trong `50..56`, bước 3 trong `56..60`. Outro bước 0 ở `_P` hoặc `_MP`, các bước sau hạ dần, bước cuối của `castillo` ở `_PP`. Bước nào của một cửa ghi mức riêng thì mức đó thắng lưới chung. Intro Fandanguillo bước 0 là hợp âm staccato `_MF` (64), có accent. Fandanguillo, Danza, Alcaniz và Olite khép ở `_MF`, không tan về `_PP`. Fandanguillo và Danza khép staccato. Alcaniz cắt ngắn lead của ô cuối. Olite khép bằng hai hợp âm staccato. `apply_guitar_wave` cộng `round(C) - 64` cho cả ô sau khi nốt đã viết.

Độ nổi của cửa nằm ở hai lớp, cả hai viết ra trước khi sóng chạy.

- Qua các bước, cửa hát đi lên hoặc cắt. Castillo, Sonatina và Juglar mở ở mức thấp của bước đó rồi lên dần tới thân bài. Outro của ba cửa này hạ về nốt ngân `_PP`. Fandanguillo, Danza, Alcaniz và Olite khép bằng nhát `_MF` rồi nghỉ. Seam sau nhát đó gặp intro Castillo ở `_PP`: điệu cắt, chương chậm thở.
- Trong một ô, khoảng đã viết còn nguyên vì sóng cộng cùng một lượng cho cả ô. Juglar: lead móc 0 ở mức của bước, móc 2 và móc 4 cùng cao độ và thấp hơn một nấc `_under_lead`. Alcaniz: lead ngân `duration_beats = 1.5` trên bass móc đơn, chỉ ô outro cuối cắt ngắn. Olite: hai hợp âm staccato ở mức của bước, hai móc dẫn sau hợp âm thứ hai không thành hợp âm thứ ba. Cửa không lấy sàn 68, không snap, không `extra` cả ô. Ba thứ đó thuộc thân bài.

Móc kép trong cửa viết `duration_beats = 0.25`, cùng cách nốt lấy đà của sonatina. Không có thẻ `<grace/>`. Không có quạt 5–6 dây ở cửa. Rasgueado nhiều dây ở lại thân bài.

### 4.1 `castillo`

Nguồn cửa: các ô ngân của *Castillos* và *Sonatina* Andante. Một nốt hát, bass buông, bè trong thưa.

- Intro ngắn, bước 0: bass `_torroba_bass` của `I` ngân cả ô, `_PP`. Lead nghỉ.
- Intro ngắn, bước 1: cùng bass, `_P`. Từ giữa ô, lead là một nốt của `I`, ngân đến hết ô. Nốt đó nằm dưới nốt giá đầu thân bài không quá một quãng 8.
- Intro dài, bước 0: bass `I` một mình, `_PP`.
- Intro dài, bước 1: bass `I`, lead vào ở giữa ô, một nốt, `_P`.
- Intro dài, bước 2: bass `iv` (giọng thứ) hoặc `IV` (giọng trưởng), lead một nốt từ giữa ô, `_MP`.
- Intro dài, bước 3: bass `V7` nửa đầu, `_MP`. Nửa sau lead bước một bậc vào nốt giá đầu thân bài, dừng trước nốt đó một bậc, cùng `_scale_into`.
- Outro ngắn, bước 0: nốt giá của ô thân bài cuối được hát lại trên `V7`, ngân cả ô, bass một móc đơn ở móc 0, `_P`.
- Outro ngắn, bước 1: `_bell_chord` Picardy khi giọng thứ, không Picardy khi giọng trưởng, `_PP`.
- Outro dài, bước 0: nốt hát trên `iv`/`IV`, bass cả ô, `_P`.
- Outro dài, bước 1: nốt hát trên `V7`, `_P`.
- Outro dài, bước 2: bass `I`, lead nghỉ đến giữa ô rồi vào một nốt, `_PP`.
- Outro dài, bước 3: cùng hợp âm kết của outro ngắn bước 1, `_PP`.

`castillo` là cửa duy nhất của Torroba còn Picardy. Sáu cửa còn lại không gọi `_bell_chord`.

### 4.2 `sonatina`

Nguồn cửa: hai ô mở *Sonatina* I, đã là texture Dialogue trong thân bài. Cửa hát bậc của `I` và `V7`, vì ô pedal không có đường giá.

- Intro ngắn, bước 0: nửa đầu chỉ bass và support của `I`, lead nghỉ, `_P`. Nửa sau hai móc kép cùng một nốt bậc 3 hoặc bậc 5, rồi một móc đơn cùng cao độ.
- Intro ngắn, bước 1: nửa đầu cùng hình trên `V7`, `_MP`. Nửa sau `_scale_into` vào nốt giá đầu thân bài.
- Intro dài, bước 0: bass `I` cả ô, lead nghỉ nửa đầu, `_PP`.
- Intro dài, bước 1: hình gọi của bước 0 intro ngắn, trên `I`, `_P`.
- Intro dài, bước 2: hình gọi trên `V7`. Móc giữa nửa sau là hai móc kép slur, nốt thêu một bậc trên rồi nốt giải, `_MP`.
- Intro dài, bước 3: lead một nốt của `I` ngân cả ô, `_MP`. Support nhắc tiết tấu ở các móc yếu, bậc −1 trên mức support. Bass ở móc 0 và móc cuối.
- Outro ngắn, bước 0: hình gọi trên `V7`, `_MP`.
- Outro ngắn, bước 1: lead và support giữ một quãng 3 của `I`, bass ngân cả ô, `_P`. Không Picardy.
- Outro dài, bước 0: hình gọi trên `iv`/`IV`, `_P`.
- Outro dài, bước 1: hình gọi trên `V7`, `_MP`.
- Outro dài, bước 2: nốt hát ngân cả ô trên `I`, support nhắc ở móc yếu, `_P`.
- Outro dài, bước 3: quãng 3 của `I` trên bass ngân, `_PP`.

### 4.3 `fandanguillo`

Nguồn cửa: phách đầu *Suite Castellana* I. Cửa dùng hợp âm khối, không dùng quạt 5–6 dây. Quạt nhiều dây cần `divisions = 12` và tuplet khép. Cửa giữ lưới móc đơn của `guitar_frame.py`. Thân bài vẫn quạt ở ô đầu câu.

- Intro ngắn, bước 0: hợp âm khối ba tiếng của `I` ở móc 0, staccato, nốt trên viết `_MF`, có accent. Phần còn lại của ô nghỉ, `_P` trên nốt bass nếu có một nốt ngân.
- Intro ngắn, bước 1: cùng hợp âm của `V7` ở móc 0, `_MP`. Từ giữa ô, hai hoặc ba móc đơn lead đi lên vào nốt giá đầu thân bài.
- Intro dài, bước 0: hợp âm `I` staccato ở móc 0, `_P`.
- Intro dài, bước 1: hợp âm `iv`/`IV` ở móc 0, rồi một nốt lead ở phách mạnh thứ hai, `_P`.
- Intro dài, bước 2: hợp âm `V7` ở móc 0, `_MP`.
- Intro dài, bước 3: hợp âm `V7` ở móc 0, `_MF`. Nửa sau là móc đơn lead vào thân bài.
- Outro ngắn, bước 0: hợp âm `V7` staccato ở móc 0, `_MP`.
- Outro ngắn, bước 1: hợp âm `I` staccato ở móc 0, có accent, rồi nghỉ. Không nốt ngân.
- Outro dài, bước 0: hợp âm `iv`/`IV` staccato, `_MP`.
- Outro dài, bước 1: hợp âm `V7` staccato, `_MP`.
- Outro dài, bước 2: một nốt lead trên `V7`, móc 0, `_P`.
- Outro dài, bước 3: hai hợp âm `I` staccato, móc 0 và phách mạnh kế, nhát sau có accent, `_MF`.

### 4.4 `danza`

Nguồn cửa: *Suite Castellana* III. Hợp âm staccato đầu nhóm ba, rồi nốt đáp. Thân bài không chọn `danza` ở 4/4. Cửa vẫn có bước cho 4/4, vì một lời gọi ép không được rỗng. Trên 4/4, hợp âm chỉ ở móc 0, đáp ở móc 1 và 2.

- Intro ngắn, bước 0: hợp âm khối staccato của `I` ở móc 0. Trên 6/8, thêm hợp âm ở móc 3. Lead đáp ở móc kế, `_P`.
- Intro ngắn, bước 1: cùng nhịp trên `V7`, `_MP`. Nốt đáp cuối hướng vào nốt giá đầu thân bài, dừng trước một bậc.
- Intro dài, bước 0: chỉ hợp âm `I` ở móc 0, `_P`. Không đáp.
- Intro dài, bước 1: hợp âm và một nốt đáp trên `I`, `_P`.
- Intro dài, bước 2: hợp âm và đáp trên `V7`, `_MP`.
- Intro dài, bước 3: đáp cuối là móc đơn vào thân bài, `_MP`.
- Outro ngắn, bước 0: nhịp danza trên `V7`, `_MP`.
- Outro ngắn, bước 1: hợp âm `I` staccato ở móc 0 và ở móc 3 khi ô là 6/8, nhát sau có accent, rồi nghỉ.
- Outro dài, bước 0: nhịp danza trên `iv`/`IV`, `_MP`.
- Outro dài, bước 1: nhịp danza trên `V7`, `_MP`.
- Outro dài, bước 2: một nốt đáp trên `I`, `_P`.
- Outro dài, bước 3: hai hợp âm `I` staccato, `_MF`, rồi nghỉ.

### 4.5 `torroba_tremolo`

Nguồn cửa: nốt lặp của *Simancas*, thu về một cú trên mỗi đầu phách. Cửa không viết bộ ba 3:2. Bộ ba nằm ở thân bài và mới cần `divisions = 12`. Ô pedal giữ lưới móc đơn. Scheduler chỉ chọn pattern này trên 3/4. Lời gọi ép trên 4/4 hoặc 6/8 hát một nốt lead ở móc 0 và một bass ở móc 0, các móc khác nghỉ.

Hình của mọi ô cửa trên 3/4, trừ ô ngân kết: lead là bậc 3 hoặc bậc 5 của hợp âm chức năng. Móc 0 hát bậc đó, dài một phách, bass `_torroba_bass` cùng móc. Móc 2 và móc 4 nhắc cùng cao độ, dài một phách, không accent, vận tốc thấp hơn lead móc 0 một nấc `_under_lead`. Không có accent trên cửa này.

`_scale_into` chỉ thuộc ô intro cuối, và chỉ từ móc 5. Móc 0, móc 2 và móc 4 của ô đó vẫn là ba cú một nốt. Cú ở móc 4 dài một móc đơn, để móc 5 trống. Móc 5 bước một bậc về nốt giá đầu thân bài và dừng trước nốt đó. Bản 1 ô giữ cú móc 0 và cú móc 2 của bước 0, rồi lấy cú móc 4 cùng nốt dẫn móc 5 của bước 1.

- Intro ngắn, bước 0: hình ba cú trên `I`. Lead móc 0 ở `_PP`.
- Intro ngắn, bước 1: hình ba cú trên `V7`. Lead móc 0 ở `_P`. Móc 5 là `_scale_into`.
- Intro dài, bước 0: hình ba cú trên `I`. Lead móc 0 ở `_PP`.
- Intro dài, bước 1: hình ba cú trên `I`. Lead móc 0 ở `_P`. Chưa có `_scale_into`.
- Intro dài, bước 2: hình ba cú trên `iv` hoặc `IV`. Lead móc 0 ở `_MP`.
- Intro dài, bước 3: hình ba cú trên `V7`. Lead móc 0 ở `_MP`. Móc 5 là `_scale_into`.
- Outro ngắn, bước 0: hình ba cú trên `V7`. Lead móc 0 ở `_P`.
- Outro ngắn, bước 1: lead và bass của `I` ngân cả ô, `_PP`. Không Picardy.
- Outro dài, bước 0: hình ba cú trên `iv` hoặc `IV`. Lead móc 0 ở `_P`.
- Outro dài, bước 1: hình ba cú trên `V7`. Lead móc 0 ở `_P`.
- Outro dài, bước 2: lead và bass của `I` ngân cả ô, `_PP`.
- Outro dài, bước 3: cùng nốt ngân của bước 2. Hai ô cuối giống nhau là một cái kết. Không thêm hợp âm.

### 4.6 `alcaniz`

Nguồn cửa: động cơ 3/8 của *Alcañiz*, viết trên 6/8. Mỗi nhóm là hai tiếng: một lead và một bass. Lead ở móc 0 và móc 3, bass đáp ở móc 1 và móc 4, móc 2 và móc 5 không có nốt mới. Lead là bậc 3 hoặc bậc 5 của hợp âm chức năng. Không hợp âm khối, không staccato trên các ô trước ô cuối, không quạt. Scheduler chỉ chọn pattern này trên 6/8. Lời gọi ép trên 4/4 đặt lead ở móc 0 và móc 4, bass ở móc kế. Trên 3/4 chỉ móc 0 có lead, bass ở móc 1.

Trong suốt intro, và trong mọi bước outro trước ô cuối, mỗi lead ngân `duration_beats = 1.5`. Lead móc 3 của ô intro cuối cũng ngân 1,5 phách. Cao độ của nốt đó là một bước của `_scale_into`, dừng trước nốt giá đầu thân. Bass đáp ở móc 4 trong lúc lead còn ngân. Ô outro cuối cắt mỗi lead còn một móc đơn, để dừng tiếng. Nhát ở móc 3 của ô đó có accent, `_MF`. Các ô trước không ghi staccato.

- Intro ngắn, bước 0: đủ hai nhóm trên `I`, `_P`, accent ở móc 0.
- Intro ngắn, bước 1: đủ hai nhóm trên `V7`, `_MP`. Lead móc 3 lấy cao độ một nốt của `_scale_into`, rồi ngân 1,5 phách. Bass đáp ở móc 4. Móc 5 không có nốt mới.
- Intro dài, bước 0: một lead và một bass của nhóm đầu trên `I`, `_P`. Nhóm sau nghỉ.
- Intro dài, bước 1: đủ hai nhóm trên `I`, `_P`, accent ở móc 0.
- Intro dài, bước 2: đủ hai nhóm trên `V7`, `_MP`.
- Intro dài, bước 3: lead móc 0 trên `V7`, ngân 1,5 phách, `_MP`. Lead móc 3 lấy cao độ một nốt của `_scale_into`, rồi ngân 1,5 phách. Bass đáp ở móc 4. Móc 5 không có nốt mới.
- Outro ngắn, bước 0: đủ hai nhóm trên `V7`, lead ngân 1,5 phách, `_MP`.
- Outro ngắn, bước 1: lead `I` ở móc 0 và móc 3, mỗi lead một móc đơn. Bass ở móc 1 và móc 4. Nhát móc 3 có accent, `_MF`.
- Outro dài, bước 0: đủ hai nhóm trên `iv` hoặc `IV`, lead ngân 1,5 phách, `_MP`.
- Outro dài, bước 1: đủ hai nhóm trên `V7`, lead ngân 1,5 phách, `_MP`.
- Outro dài, bước 2: đủ hai nhóm trên `I`, lead ngân 1,5 phách, `_P`.
- Outro dài, bước 3: cùng ô cắt của outro ngắn bước 1.

### 4.7 `olite`

Nguồn cửa: hai hợp âm của *Olite* trên hai phách mạnh. Trên 4/4, hợp âm khối ba tiếng, staccato, ở móc 0 và móc 4. Nốt trên là bậc 3 hoặc bậc 5 của hợp âm chức năng. Móc yếu nghỉ. Hợp âm ngân sẽ lấp chỗ trống đó thành một ô hòa thanh. Nét chạy để ở thân bài. Không quạt. Scheduler chỉ chọn pattern này trên 4/4. Lời gọi ép trên 6/8 đặt hợp âm ở móc 0 và móc 3. Trên 3/4 chỉ móc 0.

Mọi ô intro còn chỗ cho móc 4 thì móc đó là hợp âm thứ hai, kể cả ô chạm thân bài. Nốt dẫn nằm ở móc 6 và móc 7 của ô intro cuối, đi về nốt giá đầu thân bằng `_scale_into`, hướng theo nốt đó. Hợp âm móc 4 đứng đúng đầu nửa sau, nên bản 1 ô vẫn giữ phách này. 1D và 1W đi kịch bản ngắn, nên bước 0 của intro ngắn đã có cả hai hợp âm.

- Intro ngắn, bước 0: hợp âm `I` ở móc 0 và móc 4, staccato, accent cả hai, `_P`.
- Intro ngắn, bước 1: hợp âm `V7` ở móc 0 và móc 4, staccato, accent cả hai, `_MP`. Móc 6 và móc 7 là `_scale_into`.
- Intro dài, bước 0: hợp âm `I` ở móc 0 và móc 4, staccato, accent cả hai, `_P`.
- Intro dài, bước 1: hợp âm `I` ở móc 0 và móc 4, staccato, accent cả hai, `_P`.
- Intro dài, bước 2: hợp âm `iv` hoặc `IV` ở móc 0 và móc 4, staccato, `_MP`.
- Intro dài, bước 3: hợp âm `V7` ở móc 0 và móc 4, staccato, accent cả hai, `_MF`. Móc 6 và móc 7 là `_scale_into`.
- Outro ngắn, bước 0: hợp âm `V7` ở móc 0 và móc 4, staccato, `_MP`.
- Outro ngắn, bước 1: hợp âm `I` ở móc 0 và móc 4, staccato, nhát sau có accent, `_MF`, rồi nghỉ.
- Outro dài, bước 0: hợp âm `iv` hoặc `IV` ở móc 0 và móc 4, staccato, `_MP`.
- Outro dài, bước 1: hợp âm `V7` ở móc 0 và móc 4, staccato, `_MP`.
- Outro dài, bước 2: một nốt lead trên `I` ở móc 0, dài một phách, `_P`, rồi nghỉ. Không có hợp âm ở móc 4. Đây là ô thở trước hai hợp âm kết.
- Outro dài, bước 3: hai hợp âm `I` ở móc 0 và móc 4, staccato, `_MF`, nhát sau có accent, rồi nghỉ.

---

## 5. Chỗ code, sau khi bảng mục 2 được giữ

Cửa của bảy pattern:

- Bảy hàm cửa trong `guitar_torroba.py`, trả `list[tuple]` cùng dạng spec của `guitar_frame.py`.
- Khóa `("torroba", "castillo")`, `("torroba", "sonatina")`, `("torroba", "fandanguillo")`, `("torroba", "danza")`, `("torroba", "torroba_tremolo")`, `("torroba", "alcaniz")`, `("torroba", "olite")` trong `DOORS` hoặc `_RETAINED_DOORS`. Khóa giữ lại thắng khóa import.
- Cửa `torroba_tremolo` không có onset `1/12`. Cửa `alcaniz` và `olite` không có quạt.
- `_torroba` giữ làm lưới khi `render_intro` được gọi không có pattern.
- Cửa `danza` vẫn có bước 4/4 cho lời gọi ép. Scheduler không chọn `danza` ở 4/4.

Ba pattern mới:

- `torroba_tremolo`, tên in **Juglar**, vào `_FAMILY`, `_PATTERN_TITLE`, `PATTERN_NAMES`, `PROFILES`, `_PEDAL_DOOR_PROFILE`, và tập extra cả ô. Profile sóng cùng hàng `sonatina`. `_torroba_contrast` của chương chậm trả id này khi mood đoạn giữa là `calm`.
- `alcaniz`, tên in **Alcaniz**, vào cùng các bảng. Profile ô điệu và ô mở đầu cùng hàng `danza`. Ô mềm cùng hàng `castillo`. Scherzo `rally` trả id này. Chỉ render trên 6/8.
- `olite`, tên in **Olite**, vào cùng các bảng. Profile ô Vivace cùng hàng `danza`. Ô thưa cùng hàng `castillo`. Chương 4/4 mood `volatile` trả id này.
- Texture thưa của Juglar, texture mở đầu và texture mềm của Alcaniz, texture thưa của Olite đăng ký trong `_FIGURES`. Điệu Zafra và điệu Redaba không đăng ký.

Giữ nguyên:

- Danza trên scherzo `calm`, và Bounce.
- `calm`, `rally`, `selloff` của 4/4. Fandanguillo trên scherzo `volatile`. B = Sonatina khi scherzo chọn Castillo, và khi đoạn giữa của chương chậm không phải `calm`.
- Tám texture hiện có, kể cả cửa tempo và cửa `k` của Arada và Float.
- Rasgueado 5–6 dây và 3–4 dây của thân bài.
- `fit_intro` / `fit_outro`, sàn, trần, số stab.
