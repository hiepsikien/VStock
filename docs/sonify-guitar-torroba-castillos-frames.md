# Pattern, texture, và cửa intro/outro của Torroba

> **Trạng thái**: định nghĩa để chốt. Chưa có trong code.
> **Khung đang chạy**: [`docs/sonify-guitar-frame-variations.md`](./sonify-guitar-frame-variations.md) mục 4. Bốn pattern và tám texture: [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md), [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md). Tên in: [`docs/sonify-pattern-names.md`](./sonify-pattern-names.md).
> **Nguồn đã đọc**: *Simancas* (tab E. Ceja), *Zafra* (bản classclef, Allegretto vivace, nốt đen = 110), *Redaba* (bản Cadencia 1973, Allegretto, 3/4, Mi trưởng, 54 ô), *Alcañiz* (bản Segovia, tab ohdan, Allegro, móc đơn = 168, 3/8, La trưởng). *Suite Castellana* đã có Fandanguillo, Danza, Arada và Float. File này không mở lại chúng.

Hai chữ đang bị dùng cho hai lớp khác nhau. Mục 1 khóa nghĩa. Mục 2 khóa form của chương không phải 1D. Mục 3 đặt Tremolo và Alcañiz thành hai pattern mới, mỗi pattern ba texture. Mục 4 là cửa intro/outro của bốn pattern đang hát.

---

## 1. Pattern và texture

**Pattern** là đơn vị scheduler khóa cho một vùng hình thức, và là tên in trên dòng chương. Một câu thuộc một pattern. Pattern có một thói quen tay phải đủ để hát cả vùng đó, một cửa intro, và một cửa outro.

Bốn pattern đang hát:

| Id | Tên in | Thói quen tay phải |
|---|---|---|
| `castillo` | Castillo | Một nốt giá ngân, bass buông. Chậm thì Arada và Float xen vào |
| `sonatina` | Sonatina | Rải và đối thoại của *Sonatina* I |
| `fandanguillo` | Fandanguillo | Điệu 3/4–6/8, quạt ở ô đầu câu |
| `danza` | Danza | Khoanh lại. Hợp âm staccato đầu nhóm ba, chỉ thân bài 3/4 và 6/8. Texture Bounce đi cùng, vì Bounce chỉ thuộc Danza |

**Texture** là cách đánh bên trong pattern đã khóa. Tám texture đang hát: Arpeggio, Rasgueado, Pizzicato, Dialogue, Arch, Bounce, Arada, Float. Mỗi texture thuộc một pattern cha, theo bảng ở [`docs/sonify-pattern-names.md`](./sonify-pattern-names.md) mục 3. Texture không có id trong `_FAMILY`, không vào `_PATTERN_TITLE`, không lên dòng chương. Ô pedal không nhận texture, vì ô pedal không có đường giá.

Một câu giữ một texture. Câu kế có thể đổi texture, hoặc về lưới nền của pattern cha. Bộ đếm `n` / `k` và bước 7 của mục 4.0 trong kế hoạch câu giữ nguyên: hai câu sát nhau không lặp cùng một số texture.

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

Bach và Barrios, khi bài dài hơn 40 ô, đi một hàng palette trước trio. Torroba không đi hàng đó. Pattern mới cũng không mở hàng palette. Nó chiếm một ô trong A hoặc trong B của bảng trên.

---

## 3. Hai pattern mới

Mỗi pattern khóa cả một vùng A hoặc một vùng B. Ba texture của nó chỉ hát khi câu đã thuộc pattern đó. Texture không lên dòng chương. 1D, 1W và các chương 4/4 giữ bảng mood hiện tại. BPM của vùng là BPM của chương.

Chữ **Tremolo** trên chart đã thuộc Barrios (`tremolo`). Pattern Torroba dùng id `torroba_tremolo`. Tên in đề xuất là **Juglar**, lấy từ phụ đề *Juglaresca* của *Simancas*. Texture tremolo bên trong vẫn mang tên đó trong code, và không vào `PATTERN_NAMES`.

### 3.1 Tremolo — id `torroba_tremolo`

Ba texture, theo thứ tự trong một vùng đã khóa pattern này. Câu tremolo được câu điệu Zafra kế tiếp đáp. Câu sau cặp đó là điệu Redaba. Bước 7 vẫn chặn hai câu sát nhau cùng một texture.

| Texture | Lấy từ | Hình đã đọc trên bản |
|---|---|---|
| tremolo | *Simancas*, và thân tremolo của *Zafra* | *Simancas* ở 3/4. Bốn ô đầu là một vòng bass Mi với bè trong thưa. Từ ô 5, giai điệu là ba cú cùng một nốt trong một phách, bass đổi chậm hơn, thường đúng phách. *Zafra* mở ở Allegretto vivace, nốt đen = 110, bằng cùng một ngón trái lặp nhiều cú rồi một nốt bass buông |
| Điệu Zafra | Phần điệu sau tremolo trong *Zafra* (*Fantasmas*) | Chỗ ngón trái đổi từng cú, cùng tempo 110, có accent. Khoảng ô 45–53 là ostinato harmonic `<12>` xen nốt bấm. Cuối bản, khoảng ô 100–103, có chữ pizz. Đoạn rall về 70 (ô 54–63) là câu slur chậm của bản, không lấy vào texture này |
| Điệu Redaba | Điệu của *Redaba* | Bản Cadencia ghi **REDABA**, Allegretto, 3/4, Mi trưởng, 54 ô. Đây là bản đang gọi là Rebada. Phần điệu là câu allegretto mở đầu và câu trở lại *a tempo* ở ô 19, mức *f*, sau đoạn *pp* và *rit.* Bản in còn *cediendo*, *dim.*, và *ff* về sau. Lưới từng móc của điệu này chưa chốt, vì lớp chữ của PDF không đủ nốt |

Tremolo của Torroba là ba cú giai điệu trong một phách, bass trên phách. Id `tremolo` và hàng offset bốn móc kép của Barrios giữ cho Barrios.

Chỗ trong form: chương chậm có bridge (1M II, 3M II, chương giữa của 1Y, 3/4, BPM ≤ 72). A vẫn là Castillo. B là Tremolo. A trở lại Castillo. Dòng chương là `Castillo — Juglar — Castillo`. Sonatina vẫn là rally và selloff của mọi chương 4/4.

### 3.2 Alcañiz — id `alcaniz`, tên in **Alcaniz**

Bản là *Alcañiz (Festiva)* trong *Castillos de España*, bản Segovia. Allegro, móc đơn = 168, nhịp 3/8, giọng La trưởng. Engine không có nhịp 3/8. Trên scherzo 6/8, một ô 6/8 chứa hai nhóm 3/8. Trên 3/4, một ô 3/4 chứa hai nhóm 3/8.

Ba texture, lấy từ ba đoạn khác nhau của cùng bản:

| Texture | Đoạn trên tab Segovia | Hình tay phải |
|---|---|---|
| Mở đầu | Khổ lặp đầu, có ending 1 và ending 2 | Phách đầu: bass Mi buông và một hợp âm. Rồi một nét pull-off trên dây Si (`0-5-kéo-4-5-7`). Ô sau là song thanh đi xuống: dây Mi `9-7-5` trên dây Rê `7-6-4`, giải bằng `4-búa-5-4-2` cũng song thanh. Ending 1 là một nốt lấy đà rồi cadence kéo về đầu khổ |
| Điệu | Động cơ 3/8, rõ nhất sau dấu coda và ở bước lặp ba lần | Nốt giai điệu đen chấm, bass đáp bằng móc đơn (Mi `0`, Si `1`, Sol `0`, bass La `3`). Rồi hai móc đơn bè trong (Rê `4` rồi `2`). Bước lặp: Mi `2`, Si `0-2`, Sol `3`, bass Mi `2`, ba lần, rồi một nét `4-2-0` |
| Mềm | Sau ending 2, chữ *To Coda*, trước đoạn móc ba mươi hai | Nét slur đi xuống `2-búa-4-kéo-2-0`. Giai điệu thưa trên một pedal, bè trong `4-kéo-2-1`, bass `4-2-4`. Trường độ mở ra đen chấm và một nốt tròn. Ô harmonic cuối (`<12>` rồi hợp âm harmonic dây buông) là ô khép của coda, thuộc texture này. Đoạn móc ba mươi hai là nét nối vào *D.C.*, cùng vai nét chạy ngắn đã có, không thành texture thứ tư |

Chỗ trong form, sau khi Danza được khoanh: scherzo `calm` hôm nay là Danza. Ô đó đổi thành Alcaniz, vì *Alcañiz* viết ở 3/8 và một ô 6/8 chứa đúng hai nhóm 3/8. B vẫn là Castillo. Dòng chương là `Alcaniz — Castillo — Alcaniz`. Scherzo `selloff` giữ A là Castillo và B là Sonatina. Scherzo `rally` và `volatile` vẫn là Fandanguillo, B vẫn là Castillo.

### 3.3 Olite — id `olite`, tên in **Olite**

*Olite* trong *Castillos de España*. Bản Cadencia ghi phụ đề *Fiesta del Rey Noble*. Vivace, nốt đen = 95, nhịp 2/4, giọng La trưởng, 109 ô.

Đây là một pattern, không phải figure.

Figure phải nằm trong một pattern cha và chỉ hát một câu. Danza đang được khoanh, nên Olite không có cha là Danza. Fandanguillo là điệu 3/4–6/8, quạt ở móc 0. Alcañiz là điệu 3/8. Tremolo là ba cú giai điệu một phách rồi một điệu 3/4. *Olite* là điệu đôi: những ô đầu khóa barre II và nhắc hợp âm, rồi một nét chạy ngắn (các bậc kiểu `5-5-4-2-3-2-0`, `0-2-4`). Accent nằm trên hợp âm. Thân Vivace chạy đến khoảng ô 63. Ô 64–68 rall. Ô 69–89 là Lento, nốt đen = 60, giai điệu đi từng nốt. Ô 90, *Tempo 1*, nốt đen = 95, điệu đôi trở lại đến ô 109.

Điệu Vivace đủ hát cả một vùng. Lento của bản là đoạn giữa của chính *Olite*, cùng vai vùng B. Pattern Olite chỉ giữ điệu nhanh. Vùng B của chương vẫn là pattern khác.

Engine không có nhịp 2/4. Hai ô 2/4 thành một ô 4/4: phách 0 và phách 4 mỗi phách là một hợp âm của điệu, nét chạy nằm trong phách. `danza` không đứng ở 4/4. Olite đứng đúng chỗ đó.

Chỗ trong form: mọi chương 4/4, mood `volatile`, hôm nay là Fandanguillo. Ô đó đổi thành Olite. Fandanguillo giữ scherzo `rally` và `volatile`. `calm` 4/4 vẫn là Castillo. `rally` và `selloff` 4/4 vẫn là Sonatina. 1D `volatile` vì thế hát Olite cả thân.

Ba pattern mới có cửa intro/outro cùng dạng mục 4: bản ngắn hai bước, bản dài bốn bước, profile `"torroba"`, không quạt 5–6 dây trên ô pedal. Kịch bản cửa và lưới từng móc viết sau khi các chỗ trên được giữ.

---

## 4. Cửa theo pattern

Bốn pattern đang hát sẽ mở và khép bằng cửa riêng. Hôm nay cả bốn đi `torroba_frame`: `calm` và `rally` hát một nốt giá trên bass buông, `volatile` và `selloff` đánh một hợp âm khối ở móc 0, ô outro cuối giọng thứ là Picardy.

`render_intro` / `render_outro` rẽ theo `(ensemble, pattern)` khi pattern có cửa trong `DOORS`. Bốn id chưa có cửa, nên mọi chương đi `_torroba` trong `guitar_frame.py`.

Mỗi pattern có một kịch bản ngắn (bước 0–1) và một kịch bản dài (bước 0–3). `frame_roles` và `_compressed` giữ nguyên. Bản 1 ô vẫn cắt đôi bản ngắn.

Cửa đọc pattern, không đọc mood. Picardy chỉ còn ở outro của `castillo`. Fandanguillo, Danza và Sonatina khép bằng hợp âm của điệu.

Cửa hát hợp âm chức năng `I`, `iv`/`IV`, `V7` qua `_function`, cùng cách cửa Bach và Sor. Giọng thứ giữ bậc 3 thứ, trừ ô outro cuối của `castillo`.

Bước nào `frame_roles` lặp thì ô giống hệt. `_compressed` giữ nửa đầu bước 0 và dựng bước 1 vào nửa sau. Nốt dẫn vào thân bài nằm ở bước 1, từ móc `epb // 2` trở đi, để bản 1 ô không nuốt nó.

Profile ô pedal của cả bốn cửa là `"torroba"`. `_PEDAL_DOOR_PROFILE` đã có bốn khóa này. Trần bass 53 và cửa bè trung trên 65, khi còn dưới bè cao, giữ nguyên. Ô pedal không đi qua `_plant_pickup`.

Vận tốc viết theo bậc thang của [`docs/sonify-guitar-frame-variations.md`](./sonify-guitar-frame-variations.md) mục 4.2. Intro bước 0 ở `_PP` (46), bước 1 ở `_P` (50), bước 2 trong `50..56`, bước 3 trong `56..60`. Outro bước 0 ở `_P` hoặc `_MP`, các bước sau hạ dần, bước cuối của `castillo` ở `_PP`. Fandanguillo và Danza khép ở `_MF` (64), staccato, không tan về `_PP`. `apply_guitar_wave` vẫn cộng `round(C) - 64` sau đó. Hiệu trong ô giữ nguyên.

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

`castillo` là cửa duy nhất của Torroba còn Picardy. Ba cửa kia không gọi `_bell_chord`.

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

---

## 5. Chỗ code, sau khi mục 1–3 được giữ

Cửa của bốn pattern hiện có:

- Bốn hàm cửa trong `guitar_torroba.py`, trả `list[tuple]` cùng dạng spec của `guitar_frame.py`.
- Khóa `("torroba", "castillo")`, `("torroba", "sonatina")`, `("torroba", "fandanguillo")`, `("torroba", "danza")` trong `DOORS` hoặc `_RETAINED_DOORS`. Khóa giữ lại thắng khóa import.
- `_torroba` giữ làm lưới khi `render_intro` được gọi không có pattern.

Hai pattern mới, khi được giữ:

- `torroba_tremolo` vào `_FAMILY`, `_PATTERN_TITLE` (**Juglar**), `PATTERN_NAMES`, `PROFILES`, và `_PEDAL_DOOR_PROFILE`. `_torroba_contrast` của chương chậm (`bpm <= 72`) trả id này.
- `alcaniz` vào cùng các bảng, tên in **Alcaniz**. Scherzo `calm` trả id này thay cho `danza`. B của scherzo đó vẫn là `castillo`.
- `olite` vào cùng các bảng, tên in **Olite**. Chương 4/4 mood `volatile` trả id này thay cho `fandanguillo`.
- Sáu texture của Tremolo và Alcañiz đăng ký trong `_FIGURES`, mỗi texture chỉ khi pattern của câu là pattern cha của nó. Olite là lưới của chính pattern, chưa có texture con.
- Trong `torroba_tremolo`, câu tremolo được câu điệu Zafra đáp, rồi tới điệu Redaba.
- `danza` rời `_torroba_primary`. Texture Bounce không còn được gọi.

Giữ nguyên:

- `calm`, `rally` và `selloff` của 4/4. Khóa một pattern của 1D. Fandanguillo trên scherzo `rally` và `volatile`. B = Castillo khi scherzo chọn Fandanguillo. B = Sonatina khi scherzo chọn Castillo.
- Tám texture hiện có, kể cả cửa tempo và cửa `k` của Arada và Float.
- Rasgueado 5–6 dây và 3–4 dây của thân bài.
- `fit_intro` / `fit_outro`, sàn, trần, số stab.
