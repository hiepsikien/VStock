# Intro và outro guitar: tình trạng hiện có và cửa riêng cho từng pattern

> **Phạm vi**: khung ở `backend/app/sonify/guitar_frame.py`, 28 pattern thân bài trong `PROFILES` của `backend/app/sonify/guitar_wave.py`, và chỗ `_paint_frames` / `_smooth_boundaries` gọi khung đó.
> **Mục tiêu**: mỗi pattern có một loại intro và một loại outro. Bản ngắn và bản dài vẫn là hai độ dài của cùng một kịch bản.

Tài liệu này ghi khung đang chạy, rồi chốt cửa mới đến từng bước. Chưa đổi code phát nhạc.

Mốc móc đơn dưới đây là chỉ số eighth `0 .. epb - 1`. Ví dụ 4/4 dùng `epb = 8`. 6/8 và 3/4 đi theo cell của chính thân bài; bước nào cần móc kép hoặc chùm 6 thì gọi đúng lưới đó. Velocity viết sẵn: `_PP = 46`, `_P = 50`, `_MP = 56`, `_MF = 64`. Thân bài hát ở `_MELODY = 64`, bass `_BASS = 56`, bè trong `_INNER = 46`.

---

## 1. Tình trạng hiện có

`render_intro` / `render_outro` vẽ vùng pedal (`intro`, `warmup`, `outro`, `cooldown`). Giá ở đó là một nốt đóng cửa lặp lại, nên khung bỏ qua đường giá và viết một cửa nhạc.

Bộ chọn là `_frame_composer`: `bach`, `villa`, `barrios`, `brouwer`, còn lại là Sor (`classic`). Độ dài chỉ đổi số bước của **cùng một kịch bản**:

- 1 ô: `_compressed` cắt đôi kịch bản ngắn, nửa đầu là bước 0, nửa sau là bước 1.
- 2 ô: kịch bản ngắn, hai bước.
- 3 ô trở lên: kịch bản dài, bốn bước, kéo giãn bằng `frame_roles`. Ô cuối luôn là bước cuối, để cadence vẫn giải.

Ba nhánh phụ không đọc tên pattern thân bài:

| Nhánh | Điều kiện | Ảnh hưởng |
|---|---|---|
| Bach vũ điệu / phức điệu | `_bach_dance`: `character` không phải `volatile` hay `selloff`, và `bpm > 72` | Cả intro và outro |
| Brouwer edge / trữ tình | `ctx.character` là `volatile` hoặc `selloff` | Cả intro và outro. Đọc character cả chương, không đi theo `character_at` từng ô |
| Villa sáng | `_frame_mood` là `rally` hoặc `volatile` | Chỉ outro. Intro Villa không tách |

28 pattern thân bài dùng **7 họ intro** và **8 họ outro**. Họ outro thứ tám là stab cuối của Villa khi mood sáng. Short và long không tính thêm một họ.

### 1.1 Sor — một cửa cho năm pattern

Pattern: `cantabile`, `elegiaque`, `study`, `mozart_var`, `galop`.

- **Intro ngắn**: Introduction kiểu Mozart Op. 9. Ô 0 là hợp âm I, bass ngân, bè trên chấm dôi Pháp (`_overture_cells`). Ô 1 là bass V7 chấm dôi rồi scale vào thân bài.
- **Intro dài**: I staccato, đi bộ lyric với quãng 6 hoặc quãng 3, V7 chấm dôi, scale trên I.
- **Outro ngắn**: V7 gọn (`_compact`), rồi block I.
- **Outro dài**: bass đi I–IV–V, hai ô V7 chấm dôi, block I ở thế cao.

### 1.2 Barrios — một cửa cho tám pattern

Pattern: `preludio`, `andante`, `thumb_cantabile`, `tremolo`, `choro`, `polca`, `hemiola`, `vals`.

- **Intro ngắn**: chuông hòa âm (`_bells`), rồi bass I thức dưới arpeggio đi lên.
- **Intro dài**: chuông, cantabile, arpeggio trên ii, cadence nhường thân bài (`_barrios_intro_cadence`).
- **Outro ngắn**: I thưa (`_sparse`), rồi chuông Picardy.
- **Outro dài**: I thưa, cantabile pp, ii gọn, chuông Picardy.

### 1.3 Villa-Lobos — một intro, outro tách khi sáng

Pattern: `chord_melody`, `thumb_cantabile`, `villa_pattern`, `etude1`, `etude11`.

- **Intro ngắn**: roll dây buông trên I, rồi hai stab đảo phách về bass buông.
- **Intro dài**: hai ô roll, một ô đi lên, ô cuối là block có accent rồi ngân.
- **Outro ngắn**: đi lên rồi roll. Nếu sáng và là ô cuối: stab.
- **Outro dài**: roll, pedal dây buông, đi lên, rồi stab khi sáng hoặc chuông khi không sáng.

### 1.4 Brouwer — hai cửa theo character cả chương

Pattern: `noviembre`, `sarabande`, `brouwer_etude`, `elogio_pizz`.

- **Edge** (`volatile`, `selloff`): intro là stab rồi chạy; bản dài là accent dây buông, bass ngập ngừng, stab song song, dồn. Outro là khối đảo phách rồi stab-và-ngân; bản dài thưa, đi lên, hợp âm rộng, một accent dây buông.
- **Trữ tình**: intro là bass buông sâu rồi color roll; bản dài là một chuông, cantabile, color roll, I ổn định. Outro là I thưa rồi chuông Picardy; bản dài là roll mỏng, bước chủ, phách 2 treo, chuông Picardy.

`brouwer_etude` ở rally đi cửa trữ tình. Cửa edge đọc `ctx.character` cả chương, không đọc pattern từng ô. Sarabande khi `bpm <= 72` mà character không phải `selloff` hay `volatile` vẫn đi cửa trữ tình. Chương `selloff` có trio thì thân bài của trio là `brouwer_etude`, vì `_brouwer_contrast` trả motor cho ballad, và cửa vẫn là edge.

### 1.5 Bach — hai cửa theo nhịp và character

Pattern: `bach_sarabande`, `bach_gavotte`, `bach_bourree`, `bach_fuga`, `bach_gigue`, `bach_chaconne`.

- **Vũ điệu** (Bourrée, Gavotte, Gigue bị gộp): intro ngắn là anacrusis I rồi chạy V7. Intro dài là pickup staccato, tetrachord bước xuống, mordent, scale lấy đà. Outro ngắn là nửa kết rồi block I. Outro dài là tetrachord, flourish V7, mordent, block I.
- **Phức điệu** (Fuga, Sarabande, Chaconne bị gộp): intro ngắn là arpeggio pedal rồi hàng xóm trên V7. Intro dài là subject, answer, hội tụ về V7, block I. Outro ngắn là I thưa rồi Picardy. Outro dài là pedal V7, pedal I, arpeggiato I+, Picardy.

`_bach_dance` không đọc pattern. Sarabande 3/4, bpm trên 72, character calm vẫn nhận cửa vũ điệu trong khi `_bach_primary` chọn `bach_sarabande`.

### 1.6 Pattern nào kề pedal

`_bar_pattern` trên một ô pedal trả về `"pedal"`. Intro phải đọc ô thân bài đầu, `leading[-1] + 1`. Outro phải đọc ô thân bài cuối, `trailing[0] - 1`. Hết thân bài thì lấy `headline_id`.

Form dài đi `_assign_macro`. Nhánh này không có `_barrios_palette` hay `_barrios_region_patterns`.

- Có trio hoặc cầu: cả nhóm A một pattern từ `_dominant_pattern`, cả nhóm B một khách từ `_contrast_pattern`. Form guitar có khách là A–B–A (slot 0, slot 1, slot 2). Ô thân bài cuối là A.
- Không có contrast và `bars > 40`: mỗi `regime_slot` tự gọi `_dominant_pattern`. Ô cuối không bị buộc nhắc lại pattern mở.
- `bars <= 40` và không có contrast: cả thân bài một pattern.

`_dominant_pattern` không trả `vals` hay `thumb_cantabile` của Barrios. Hai pattern đó chỉ ra từ `_contrast_pattern`, và chúng đứng giữa chương. `month_specs("guitar")`, `quarter_specs`, và `year_specs` không có chương hai vùng kết bằng khách. Intro và outro của hai cửa này im trên form đang chạy. Mục 7 không vẽ cửa ở biên A|B, nên hai kịch bản ở mục 6.3 chưa được phát. Chúng nằm trong catalog cho đợt sau, khi một form đặt chính pattern đó kề pedal.

`thumb_cantabile` của Villa là pattern mở khi `selloff`. Cửa intro và outro của nó kêu trên chương đó.

26 pattern còn lại đều có lúc đứng kề pedal đầu hoặc pedal cuối. Bộ chọn thân bài nằm ở `_dominant_pattern`, với nhánh trong `guitar_bach.py`, `guitar_sor.py`, `guitar_barrios.py`, và `guitar_brouwer.py`.

---

## 2. Vì sao nghe lặp

Cùng một tác gia, cùng một kịch bản, dù thân bài đã đổi chất:

- Galop và Elegiaque cùng mở Op. 9.
- Choro và Andante cùng mở chuông Preludio.
- Etude 1 và chord melody cùng roll dây buông.
- Bourrée, Gavotte, Gigue dùng một cửa vũ điệu.
- Fuga, Sarabande, Chaconne dùng một cửa phức điệu.
- Noviembre và Sarabande của Brouwer dùng một cửa trữ tình khi chương không ở trạng thái edge.

Độ dài 2 ô và 4 ô không tách được các cặp này. Đường lực `fit_intro` / `fit_outro` chỉ trượt tâm velocity. Hình nốt trong ô vẫn là một cử chỉ.

---

## 3. Cách gắn cửa mới

1. Intro đọc pattern ô thân bài đầu. Outro đọc pattern ô thân bài cuối. Xem mục 1.6.
2. Khóa là `(ensemble, pattern)`, không chỉ `ensemble`. Ba cờ `_bach_dance`, edge cả chương, và mood sáng của mọi pattern Villa thôi không chọn cửa.
3. Mỗi pattern có một kịch bản ngắn (bước 0–1) và một kịch bản dài (bước 0–3). `frame_roles` và `_compressed` giữ nguyên.
4. Tám pattern dưới mục 5 giữ một phần cửa cũ. Hai mươi pattern còn lại viết cả intro lẫn outro. Study và Mozart chia đôi cặp Sor đang dính liền, nên đếm pattern giữ cửa cũ là tám.
5. Kịch bản `vals` và thumb Barrios được viết ở mục 6.3. Đợt này không phát chúng. Xem mục 1.6.
6. Công thức `fit_intro` / `fit_outro`, sàn, trần, và các số stab `70 / 66 / 62` giữ nguyên. Điều kiện bật stab Villa thì đổi, mục 4.5.

Picardy chỉ giữ ở `preludio`, `noviembre`, `bach_fuga`. Galop, choro, vals, sarabande, chaconne, và elegiaque kết bằng hợp âm của điệu.

---

## 4. Quy tắc tại biên

### 4.1 Chữ ký

`_paint_frames(ctx, patterns, lead, support, low)` tính:

- `intro_pattern = _bar_pattern(ctx, leading[-1] + 1, patterns)` khi ô đó còn trong chương và không phải pedal, nếu không thì `headline_id(ctx, patterns)`.
- `outro_pattern = _bar_pattern(ctx, trailing[0] - 1, patterns)` theo cùng quy tắc.

Rồi gọi `render_intro(ctx, leading, intro_pattern)` và `render_outro(ctx, trailing, outro_pattern)`. `_gesture` rẽ theo `(ctx.ensemble, pattern)`.

Ô một nhịp đi `_gesture` với `length == 1`. Hàm đó gọi `_compressed`, rồi `_gesture_body`. `_gesture_body` không đi qua `_gesture` lần nữa. Cả `_gesture`, `_compressed`, và `_gesture_body` đều nhận pattern.

### 4.2 Velocity viết sẵn và tâm ô

`render_intro` và `render_outro` chạy trước `apply_guitar_wave`. Lúc viết nốt chưa biết fit sẽ bẹt hay giữ đường, vì `L` phụ thuộc chính velocity vừa viết. Hai nhánh đó không cùng thành một hàm.

Chốt: viết bậc thang của mục 6. `apply_guitar_wave` cộng `round(C) - 64` cho cả ô sau đó. Khi fit không bẹt, đường tâm dốc thêm lên bậc thang. Khi fit bẹt, bậc thang là độ nổi còn lại. Hiệu `V_written - 64` bên trong ô vẫn còn.

Bậc thang của cửa mới:

- Intro: bước 0 ở `_PP`, bước 1 ở `_P`, bước 2 trong `50..56`, bước 3 trong `56..60`, hướng tới lead 64 / bass 56 / bè trong 46 của thân bài. Bước 3 của galop, choro, polca, và hemiola ở `_MF` (64). Đó là pickup vào thân bài, không bị trần `56..60` kéo xuống. `elogio_pizz` cũng lên `_MF` ở bước này.
- Outro: bước 0 đón thân bài ở `_MP` hoặc `_P`. Các bước sau hạ dần. Cadence của Bourrée, Gavotte, Gigue, Study, và Mozart giữ `_P`. Câu velocity ở từng pattern thắng câu này.

Galop, choro, polca, và `elogio_pizz` khép bằng hợp âm staccato, bước cuối ở `_MF`, không tan về `_PP`. Hemiola khép bằng block I rồi ngân, bước cuối ở `_P`. Mục 6 là câu được code.

Chuông, chấm dôi Pháp, và Picardy giữ contour đã viết (`_BELL_CONTOUR`, `_overture_cells`, `_bach_picardy`). Không kéo các contour đó về bậc thang chung.

### 4.3 Nối nhịp

Nửa sau của bước intro cuối chuẩn bị cell và âm vực của ô thân bài đầu. `_scale_into` vẫn dừng trước nốt giai điệu ô sau một bậc.

`_smooth_boundaries` đang gọi `_plant_pickup` trên `leading[-1]`. Ô đó có kind pedal, `_bar_pattern` trả về `"pedal"`, và `_plant_pickup` xóa bass ở móc đơn cuối rồi ghi root hoặc fifth ở velocity 50. Nhát đó đè anacrusis Bourrée, nửa ô Gavotte, pre-tremolo, hơi thở etude, và approach của choro.

Ô pedal không đi qua `_plant_pickup`. Móc đơn cuối của intro thuộc về khung.

Ô thân bài cuối, ngay trước outro, giữ `_relax_texture` và pickup như hiện tại. Bước 0 của outro là hậu dư của cell thân bài: etude và preludio giãn từ móc kép xuống móc đơn, tremolo giãn từ nốt lặp, điệu nhảy giữ một ô nhịp của chính nó rồi mới cadence.

### 4.4 Lưới và cữ tay

Spec mặc định vẫn là móc đơn, render bằng `_eighth_event`.

Móc kép, qua `_spell16`, chỉ khi thân bài đã khắc lưới đó: `preludio`, `etude1`, `choro`, `polca`, `hemiola`, mordent và bariolage của Bach. Chương có `etude11` đã khắc division 12, nên cửa của pattern đó được dùng chùm 6.

Tremolo ở biên là nốt lặp trên lưới móc kép, cùng một cao độ, ở nửa sau bước intro cuối và nửa đầu bước outro 0. Không gọi full `_tremolo` từ im lặng, và không thêm móc ba mươi hai vào khung.

`thumb_cantabile` của Barrios và của Villa: voice 3 được lên tới `64 - ctx.semitones`, đúng trần `_place_thumb`. `_bass_hi` của mọi cửa khác giữ `53 - ctx.semitones`.

`_PROFILE["pedal"]` đang là `study`. Profile đó từ chối bass trên 53, và từ chối cả lament lẫn approach nửa cung. Ô pedal lấy profile của cửa, không lấy hàng `"pedal"`:

- Hai cửa thumb: `thumb_cantabile`.
- `elegiaque`: `elegiaque`, để lament qua được. Approach nửa cung mà không phải lament vẫn bị profile này loại.
- `choro`: `barrios_dance`, để approach nửa cung qua được.

Cửa nào viết lament hoặc approach mà profile `study` loại thì cũng đổi profile theo pattern thân bài. Các cửa còn lại giữ profile pedal hiện có.

### 4.5 Stab sau sóng

`_apply_stabs` có hai đường:

- `staccato` và `accent` cùng lúc trên ô pedal: gán `70 / 66 / 62`. Galop, choro, polca, và elogio đi đường này. Giữ nguyên. Hemiola khép bằng hợp âm ngân, không đi đường này.
- `villa_stab`: hiện bật cho mọi accent Villa ở ô pedal cuối khi mood ô đó là `rally` hoặc `volatile`. `etude11` là volatile, nên một accent kết bài bị kéo thành stab của `villa_pattern`.

Đổi điều kiện `villa_stab`: pattern ô thân bài kề outro là `villa_pattern`, và mood của ô thân bài đó là `rally`. `villa_pattern` ở mood `volatile` hôm nay có stab. Spec này bỏ stab đó. Accent kết của `etude11` chỉ là nhấn trong velocity đã viết, không kèm `staccato`, và không đi qua `villa_stab`.

### 4.6 Bước lặp

`frame_roles` lặp bước. Bước lặp là cùng một ô. Bước nào cần đổi thì nói rõ và dùng `index`, như `_roll` của Villa. Vùng cửa là warmup dính intro, hoặc outro dính cooldown, vì cả hai kind đều nằm trong `_PEDAL`. `attach_frame` chỉ gắn warmup và cooldown cho 1M, 3M, và 1Y.

| Form | Vùng mở | Vùng khép |
|---|---|---|
| Ngày | 2, kịch bản ngắn | 2 |
| Tuần | 4, mỗi bước một lần | 4 |
| 1M chương I và 3M chương I, 4/4 | 8, mỗi bước hai lần | 8 |
| 1M finale và 3M finale, 4/4 | 8 | 12: outro thân 8 cộng cooldown 4 |
| 1M chương chậm, guitar 3/4 | 10: warmup 6 cộng intro 4 | 6. Chương này không có outro trong thân, chỉ cooldown |
| 3M chương chậm, guitar 3/4 | 10 | 10: outro thân 4 cộng cooldown 6 |
| 1M scherzo, guitar 6/8 | 10 | 10: outro thân 4 cộng cooldown 6 |
| 1Y 4/4 | 6: warmup 2 cộng intro 4 | 6 |
| 1Y 3/4 | 7: warmup 3 cộng intro 4 | 7 |
| 1Y closer, guitar 6/8 | 7 | 9: outro thân 6 cộng cooldown 3 |
| 1Y finale, 4/4 | 6 | 10: outro thân 8 cộng cooldown 2 |

`frame_roles(6)` là `[0, 0, 1, 2, 2, 3]`. `frame_roles(7)` là `[0, 0, 1, 1, 2, 2, 3]`. `frame_roles(8)` là `[0, 0, 1, 1, 2, 2, 3, 3]`. `frame_roles(9)` là `[0, 0, 0, 1, 1, 2, 2, 3, 3]`. `frame_roles(10)` là `[0, 0, 0, 1, 1, 2, 2, 2, 3, 3]`. `frame_roles(12)` là `[0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3]`.

Cadence của finale 1M và 3M là ba ô của bước 3. Closer 1Y là hai ô. Bước 3 không biến theo `index` thì các ô đó giống hệt, kể cả hợp âm kết. `frame_roles(3)` trả `[0, 2, 3]` và bỏ bước 1. Form guitar hiện không có vùng cửa đúng 3 ô, nên answer của fuga và mô-típ rondeau của gavotte vẫn kêu.

---

## 5. Phần cửa cũ được giao về một pattern

| Pattern | Phần giữ | Phần rời khỏi pattern này |
|---|---|---|
| `mozart_var` | Intro ngắn `_sor_intro_short`, intro dài `_sor_intro_long`. Outro dài giữ bass I–IV–V và chấm dôi V7, thêm turn ở bước 2 | Outro ngắn V gọn về `study` |
| `study` | Outro ngắn `_sor_outro_short`: `_compact` trên V7 rồi block I | Intro Op. 9 về `mozart_var`. Outro dài viết mới, mục 6.2 |
| `preludio` | Intro ngắn/dài và outro ngắn/dài Barrios hiện có, kể cả chuông Picardy | Bảy pattern Barrios còn lại |
| `villa_pattern` | Intro ngắn/dài Villa hiện có. Outro roll, pedal, đi lên. Stab sáng chỉ còn khi pattern này và mood `rally` | `chord_melody`, thumb Villa, `etude1`, `etude11` |
| `noviembre` | Cửa trữ tình Brouwer: chuông, cantabile, color roll, I ổn; outro roll mỏng, bước chủ, phách 2, chuông | `sarabande`, `brouwer_etude` |
| `elogio_pizz` | Cửa edge: stab, bass ngập ngừng, stab song song, dồn; outro khối đảo phách rồi stab. Intro ngắn thêm một slap ở móc đơn 3. `_edge_stab` hiện chưa có nhát đó | Không còn bật edge theo character cả chương |
| `bach_bourree` | Intro ngắn `_bach_tonic_anacrusis` rồi `_bach_dominant_run`. Outro ngắn `_bach_half_cadence` rồi `_bach_block` | Tetrachord của intro dài về `bach_chaconne`. Gavotte và Gigue viết cửa riêng |
| `bach_fuga` | Intro dài giữ `_bach_subject`, `_bach_answer`, `_bach_converge_dominant`. Outro ngắn và outro dài đều viết lại theo mục 6.1, và cả hai kết bằng `_bach_picardy` | Pedal arpeggio của intro ngắn và `_bach_arpeggiato` rời cửa này. Không giữ nguyên hàm outro phức điệu cũ |

---

## 6. Cửa theo pattern

Bản một ô vẫn cắt đôi bản ngắn bằng `_compressed`. Bản ngắn là hai bước. Bản dài là bốn bước. Bước nào `frame_roles` lặp thì ô giống hệt, trừ bước nói biến theo `index`. Xem mục 4.6.

### 6.1 Bach

**`bach_bourree`** — 4/4, không calm, không volatile/selloff, bpm trên 72. Thân bài: khi lead ngân, bass đi hai móc đơn lấy đà; khi lead chạy, bass giữ nốt đen. Cell `_bourree_cells` là `(0, 4)` và `(4, 4)`.

- Intro ngắn, bước 0: `_bach_tonic_anacrusis`. Bass I phách 1 ở `_P`, ba móc đơn cuối ô.
- Intro ngắn, bước 1: `_bach_dominant_run`. V7 nửa đầu ở `_MP`, nửa sau scale vào nốt đầu thân bài.
- Intro dài, bước 0: `_bach_staccato_pickup`. Hợp âm I staccato ở móc đơn 0, bass ngân phần còn lại, `_P`.
- Intro dài, bước 1: walking bass Baroque `I → IV → V`, nốt đen xen hai móc đơn lấy đà kiểu BWV 996, `_P`. Tetrachord không còn ở bước này.
- Intro dài, bước 2: `_bach_mordent` trên V7, `_MP`.
- Intro dài, bước 3: `_bach_upbeat_scale`, bass I nửa đầu, ba móc đơn cuối, `_MP`.
- Outro ngắn, bước 0: `_bach_half_cadence`, IV rồi V7, `_MP`.
- Outro ngắn, bước 1: `_bach_block` trên I, `_P`. Điệu thứ giữ hợp âm thứ.
- Outro dài, bước 0: walking bass `I → IV`, `_P`.
- Outro dài, bước 1: `_bach_half_cadence`, `_MP`.
- Outro dài, bước 2: `_bach_mordent` trên V7, `_MP`.
- Outro dài, bước 3: `_bach_block` trên I, `_P`.

**`bach_gavotte`** — 4/4, calm, bpm trên 72. Thân bài: hai nốt đen ở móc đơn 0 và 2, nốt ở 2 là staccato, rồi bốn móc đơn song thanh quãng 3 hoặc 6 từ móc đơn 4. Anacrusis Gavotte là nửa ô.

- Intro ngắn, bước 0: nửa đầu bass I ở `_PP`. Từ móc đơn 4, hai nốt đen song thanh quãng 3/6, nốt sau staccato, `_P`.
- Intro ngắn, bước 1: móc đơn 0–1 và 2–3 là hai nốt đen trên V7, nốt sau staccato, `_MP`. Móc đơn 4–7 là bốn móc đơn song thanh vào nốt đầu thân bài.
- Intro dài, bước 0: nửa sau ô, hai nốt đen lấy đà trên I, `_P`.
- Intro dài, bước 1: mô-típ rondeau trên IV rồi I. Hai nốt đen đầu ô, bốn móc đơn song thanh nửa sau, `_P`.
- Intro dài, bước 2: `_bach_mordent` trên V7, `_MP`.
- Intro dài, bước 3: nửa đầu bass V ngân, nửa sau đúng hai nốt đen Gavotte, `_MP`.
- Outro ngắn, bước 0: bốn móc đơn song thanh trên V7, `_MP`.
- Outro ngắn, bước 1: hai nốt đen I ở nửa đầu. Hợp âm I đầy ngân từ móc đơn 4 hết ô, `_P`.
- Outro dài, bước 0: mô-típ Gavotte trên IV, `_MP`.
- Outro dài, bước 1: bốn móc đơn song thanh trên V7, thêm mordent ở móc đơn 4, `_MP`.
- Outro dài, bước 2: I vào giữa ô, từ móc đơn 4, `_P`.
- Outro dài, bước 3: block I ba bè cả ô, `_P`.

**`bach_gigue`** — 6/8, bpm trên 72, không volatile/selloff. Thân bài theo `_gigue_plan`: bass ở 0 và 3, lead ở các phách down và pickup, bè trong ở 1, 2, 4, 5.

- Intro ngắn, bước 0: arpeggio gãy trên I. Bass nhấn 0 và 3, lead và bè trong xen móc đơn 0..5, `_P`.
- Intro ngắn, bước 1: `_bach_dominant_flourish` trên V7 suốt sáu móc đơn, `_MP`. Flourish rời nhóm vũ điệu chung và chỉ còn ở Gigue.
- Intro dài, bước 0: voice 1 một mình, sáu móc đơn gãy trên I, `_P`.
- Intro dài, bước 1: bass và bè trong vào ở 0 và 3, `_P`.
- Intro dài, bước 2: `_bach_dominant_flourish`, `_MP`.
- Intro dài, bước 3: broken chord trên V7, velocity viết `52 → 60`, khóa vào phách 1 thân bài.
- Outro ngắn, bước 0: `_bach_dominant_flourish`, `_MP`.
- Outro ngắn, bước 1: block I nhấn phách 1 rồi ngân hết ô 6/8, `_P`.
- Outro dài, bước 0: arpeggio gãy 6/8 trên IV, `_MP`.
- Outro dài, bước 1: `_bach_dominant_flourish`, `_MP`.
- Outro dài, bước 2: mordent ở phách 1, móc đơn 5 lấy đà trên V7, `_P`.
- Outro dài, bước 3: block I ngân, `_P`.

**`bach_fuga`** — `_bach_primary` chỉ trả pattern này khi mood là `volatile` và nhánh 3/4 hoặc `bpm <= 72` chưa chọn trước. 3/4 `volatile` vẫn là `bach_sarabande`. 3/4 `selloff`, biên độ từ 1,6%, không có contrast, là `bach_chaconne`. Thân bài: lead hát giá ngay, bass đáp motif cách hai ô, bè trong chỉ trên phách mạnh khi lead ngân.

- Intro ngắn, bước 0: voice 1 xướng bốn nốt subject, bass vào pedal ở nửa sau, `_P`.
- Intro ngắn, bước 1: `_bach_dominant_neighbor` với `drive=True`, treo rồi giải về V7, `_MP`.
- Intro dài, bước 0: `_bach_subject`. Chỉ voice 1, `_P`.
- Intro dài, bước 1: `_bach_answer`. Bass ở bậc V, lead đi ngược phía trên, `_P`.
- Intro dài, bước 2: `_bach_converge_dominant` trên V7, `_MP`.
- Intro dài, bước 3: nửa đầu block I, nửa sau một câu đơn âm hướng vào nốt lead đầu của thân bài, `_P` rồi `_MP`.
- Outro ngắn, bước 0: stretto, bass và lead cách nhau hai móc đơn trên V7, `_MP`.
- Outro ngắn, bước 1: `_bach_picardy`, I+, `_P`.
- Outro dài, bước 0: `_bach_pedal_upper` trên V7, `_MP`.
- Outro dài, bước 1: stretto hai bè từ V7 về I, `_P`.
- Outro dài, bước 2: `_bach_pedal_upper` trên I, bè trên đi IV rồi I, `_P`.
- Outro dài, bước 3: `_bach_picardy`, `_PP`.

**`bach_sarabande`** — 3/4, hoặc bpm từ 72 trở xuống khi chưa phải chaconne. Thân bài nhấn phách 2 (`accent` eighth là 2, riêng 6/8 là 3) bằng mordent, và có passing scale ở phách cuối khi câu hoặc hợp âm sắp đổi.

- Intro ngắn, bước 0: I. Phách 1 bass và lead ở `_P`. Phách 2 hợp âm ba bè, mordent, `accent`, `_MP`. Phách 3 ngân.
- Intro ngắn, bước 1: cùng nhịp trên V7. Phách cuối hai nốt liền bậc vào thân bài, `_P`.
- Intro dài, bước 0: sarabande trên I, trọng phách 2, `_P`.
- Intro dài, bước 1: sarabande trên IV, thứ thì iv, bass bậc 4 ở phách 2, `_P`.
- Intro dài, bước 2: sarabande trên V7, mordent ở phách 2, `_MP`.
- Intro dài, bước 3: I ở phách 1–2, phách 3 passing scale vào thân bài, `_P`.
- Outro ngắn, bước 0: trọng phách 2 trên V7, mordent, `_P`.
- Outro ngắn, bước 1: bass I ở phách 1, hợp âm I đầy từ phách 2 ngân hết ô, `_P`. Điệu thứ giữ i.
- Outro dài, bước 0: sarabande trên iv hoặc IV, `_P`.
- Outro dài, bước 1: sarabande trên V7, `_P`.
- Outro dài, bước 2: bass I, lead treo bậc 4 giải xuống bậc 3 ở phách 2, `_PP`.
- Outro dài, bước 3: block I, thứ giữ thứ, `_PP`.

**`bach_chaconne`** — selloff, và 3/4 selloff khi biên độ đủ lớn. Thân bài: ground bass bước xuống, bariolage móc kép ở bè trong và lead.

- Intro ngắn, bước 0: `_bach_tetrachord`, bốn nốt bass dưới hợp âm phách 2, `_MP`. Tetrachord rời Bourrée.
- Intro ngắn, bước 1: bariolage trên V7 ở nửa sau ô, `_MP`, vào thân bài.
- Intro dài, bước 0: ground bass và hợp âm phách 2, `_P`.
- Intro dài, bước 1: lượt ground bass thứ hai, `_MP`.
- Intro dài, bước 2: `_bach_arpeggiato` trên I, `_MP`. Hàm này rời outro phức điệu dài.
- Intro dài, bước 3: bariolage trên V7, `_MP`.
- Outro ngắn, bước 0: `_bach_tetrachord` về V7, `_MP`.
- Outro ngắn, bước 1: block I ở phách 1–2, `_P`. Điệu thứ giữ i.
- Outro dài, bước 0: `_bach_tetrachord`, `_MP`.
- Outro dài, bước 1: `_bach_arpeggiato`, `_P`.
- Outro dài, bước 2: `_bach_converge_dominant` về V7, `_P`.
- Outro dài, bước 3: block I ngân, `_P`.

### 6.2 Sor (`ensemble = "classic"`)

**`mozart_var`** — volatile. Thân bài: bass root rồi fifth, mỗi nốt nửa ô; bè trong đi liền bậc ở các móc đơn yếu `_mozart_offsets`.

- Intro ngắn: `_sor_intro_short`. Bước 0 hợp âm I và `_overture_cells`. Bước 1 bass V7 chấm dôi rồi `_scale_into`.
- Intro dài: `_sor_intro_long`. Bước 0 I staccato và pickup chấm dôi. Bước 1 `_sor_lyric_walk`. Bước 2 `_dotted` trên V7. Bước 3 scale trên I.
- Outro ngắn, bước 0: turn bậc 2–3–1–7 ở lead hoặc bè trong, trên V7, `_MP`.
- Outro ngắn, bước 1: block I, `_P`.
- Outro dài, bước 0: bass `I – IV – V`, bè trong liền bậc như `mozart_var`, `_P`.
- Outro dài, bước 1: `_dotted` trên V7, `_MP`.
- Outro dài, bước 2: turn trên V7, `_MP`.
- Outro dài, bước 3: block I ở thế cao, `_P`.

**`study`** — mặc định, rally hẹp, hoặc minor. Thân bài: bass root ở 0 và fifth ở 4; bè trong là `_study_pair` trên móc đơn yếu.

- Intro ngắn, bước 0: arpeggio I. Bass root ở 0, fifth ở 4, bè trong ở 2 và 6, lead giữ bậc 3 hoặc 5, `_P`.
- Intro ngắn, bước 1: nửa đầu cùng mẫu trên V7 ở `_MP`, nửa sau `_scale_into`.
- Intro dài, bước 0: arpeggio I thưa, một hoặc hai nốt bè trong, `_P`.
- Intro dài, bước 1: arpeggio IV, cặp bè trong đều, `_P`.
- Intro dài, bước 2: arpeggio V7, `_MP`.
- Intro dài, bước 3: nửa đầu I, nửa sau `_scale_into`, `_MP`.
- Outro ngắn: `_sor_outro_short`.
- Outro dài, bước 0: arpeggio study trên I rồi IV, `_P`.
- Outro dài, bước 1: I6/4 rồi V7, `_MP`.
- Outro dài, bước 2: arpeggio thưa trên I, `_P`.
- Outro dài, bước 3: block I, `_P`.

**`cantabile`** — calm, bpm trên 72. Thân bài: lead và bè trong đi cùng trường độ, quãng 3 hoặc 6 qua `_parallel`, bass giữ nửa ô hoặc cả ô.

- Intro ngắn, bước 0: hai bè ngân quãng 3/6, bass I ở phách 1, `_P`. Không chấm dôi.
- Intro ngắn, bước 1: cặp quãng 3/6 qua V7, liền bậc vào nốt đầu thân bài, `_MP`.
- Intro dài, bước 0: hai bè vào trước, bass nghỉ nửa ô rồi điểm I, `_PP` rồi `_P`.
- Intro dài, bước 1: `_sor_lyric_walk` qua I–IV–V, `_P`.
- Intro dài, bước 2: appoggiatura trong cặp quãng 3/6 trên V7, `_MP`.
- Intro dài, bước 3: cặp quãng 3/6 trên I vào câu hát thân bài, `_P`.
- Outro ngắn, bước 0: appoggiatura quãng 3/6 trên V7, `_P`.
- Outro ngắn, bước 1: quãng 3 của I trên bass ngân, `_PP`. Bè trong không chặn thành hợp âm khô.
- Outro dài, bước 0: song thanh I–IV, `_P`.
- Outro dài, bước 1: appoggiatura trên V7, `_P`.
- Outro dài, bước 2: quãng 3 trên I, bass chạm bậc 5 rồi bậc 1, `_PP`.
- Outro dài, bước 3: hai bè giữ quãng 3 chủ âm, `_PP`.

**`elegiaque`** — selloff hoặc bpm từ 72 trở xuống. Thân bài dùng `_march_grid`: ở 4/4 là `(0, 3, root)`, `(3, 1, step)`, `(4, 3, fifth)`, `(7, 1, step)`, kèm appoggiatura.

- Intro ngắn, bước 0: bass một mình trên `_march_grid` của i hoặc I, `_PP` lên `_P`. Lead nếu có thì giữ một âm.
- Intro ngắn, bước 1: bass lament qua V7, lead một appoggiatura bậc 6 thứ giải xuống bậc 5, `_P`.
- Intro dài, bước 0: bass `_march_grid` trên i, `_PP`. Lead nghỉ hoặc một âm trung.
- Intro dài, bước 1: appoggiatura trên bass bước xuống, `_P`.
- Intro dài, bước 2: iv rồi V7 trên `_march_grid`, `_MP`.
- Intro dài, bước 3: nửa kết trên V7, móc đơn cuối bass bước xuống, `_P`.
- Outro ngắn, bước 0: lament từ bậc 5 về bậc 1 trên `_march_grid`, lead giải appoggiatura, `_P`.
- Outro ngắn, bước 1: hợp âm i ở thế thấp, dây trầm ngân, `_PP`.
- Outro dài, bước 0: `_march_grid` với bass bước xuống liên tiếp, cùng hướng nhánh `lament` của `_render_elegiaque_bar`, `_P`.
- Outro dài, bước 1: appoggiatura trên iv rồi V7, `_P`.
- Outro dài, bước 2: chấm dôi trên i, `_PP`.
- Outro dài, bước 3: dây buông trầm ngân, `_PP`.

**`galop`** — rally rộng, trưởng, biên độ từ 1,2%. Thân bài: bass staccato ở `_galop_bass_points` (4/4 là 0 và 4, 6/8 là 0 và 3), root rồi fifth; bè trong staccato có accent ở `_galop_inner_offsets`; lead nhảy quãng 3 ở `_galop_sparkle`.

- Intro ngắn, bước 0: bass staccato root/fifth trên hai điểm galop, bè trong staccato ở phách yếu, lead nghỉ hoặc một nốt ở phách 1, `_P` lên `_MP`.
- Intro ngắn, bước 1: nửa đầu galop trên V7, nửa sau lead nhảy quãng 3 staccato, `_MP`.
- Intro dài, bước 0: bass và bè trong staccato trên I, `_P`.
- Intro dài, bước 1: sparkle trên I rồi IV, `_MP`.
- Intro dài, bước 2: galop trên V7, `_MP`.
- Intro dài, bước 3: nghỉ ngắn giữa ô, ba móc đơn staccato, `_MF`.
- Outro ngắn, bước 0: galop trên V7, `_MP`.
- Outro ngắn, bước 1: hợp âm staccato ở móc đơn 0 và ở móc đơn 2 hoặc 4, `accent` trên nhát I, rồi nghỉ. Không block ngân.
- Outro dài, bước 0: galop và sparkle trên I–IV, `_MP`.
- Outro dài, bước 1: galop trên V7, `_MP`.
- Outro dài, bước 2: V7, I, V7 staccato, `_MF`.
- Outro dài, bước 3: hai hợp âm I staccato có accent.

### 6.3 Barrios

**`preludio`** — La Catedral khi moderato rally/calm, calm nói chung, hoặc hàng dài mở bằng preludio. Thân bài: bass pedal hai ô, canto ở cữ đã nâng `_catedral_canto_pitch`, bè trong là sóng móc kép `_catedral_cell`.

- Intro ngắn: `_barrios_intro_short`. Bước 0 `_bells` ở `_PP`. Bước 1 `_rising_over_bass` trên I, `contour=True`.
- Intro dài: `_barrios_intro_long`. Bước 0 `_bells`. Bước 1 `_cantabile` có contour. Bước 2 arpeggio trên ii. Bước 3 `_barrios_intro_cadence`. Nốt cuối của `_scale_into` nằm trong cữ canto, để ô thân bài đầu không nhảy quãng 8.
- Outro ngắn: `_barrios_outro_short`. `_sparse` trên I, rồi `_bell_chord` Picardy ở `_PP`.
- Outro dài: `_barrios_outro_long`. `_sparse`, `_cantabile` ở `_PP`, `_compact` trên ii, chuông Picardy.

**`tremolo`** — finale, selloff/volatile ở moderato, hoặc nhiều nốt giữ. Thân bài: bass trên móc đơn, lead lặp trên lưới tremolo.

- Intro ngắn, bước 0: bass pedal I và một nốt lead ngân, `_P`. Chưa lặp.
- Intro ngắn, bước 1: nửa đầu lead ngân trên V7. Nửa sau lặp nốt đó bằng móc kép, velocity viết `48 → 58`.
- Intro dài, bước 0: bass và arpeggio trên I, `_PP` lên `_P`.
- Intro dài, bước 1: hai nốt lead ngân trên iv hoặc ii, `_P`.
- Intro dài, bước 2: V7, lead chạm bậc 7 hoặc bậc 5, `_MP`.
- Intro dài, bước 3: nửa đầu lead ngân trên V7, nửa sau móc kép lặp một cao độ, crescendo vào thân bài.
- Outro ngắn, bước 0: nửa đầu móc kép lặp, nửa sau giãn thành móc đơn trên cùng cao độ, `54 → 46`, bass I.
- Outro ngắn, bước 1: lead ngân một mình trên I, `_PP`.
- Outro dài, bước 0: lặp thưa trên I, bass bước xuống, `_P`.
- Outro dài, bước 1: ii hoặc iv, `_P`.
- Outro dài, bước 2: `_sparse` từ V7 về I, `_PP`.
- Outro dài, bước 3: hợp âm I ở cữ giữa, `_PP`.

**`andante`** — bpm dưới 90. Thân bài là hợp âm khối trên `_andante_grid`: 4/4 là `[0, 4]` dài `[4, 4]`; 6/8 là `[0, 3]` dài `[3, 3]`; 3/4 là cả ô, hoặc `[0, 4]` khi tới apex hay câu khép.

- Intro ngắn, bước 0: hai hợp âm khối trên lưới, I rồi IV, `_P`.
- Intro ngắn, bước 1: ii rồi V7 trên cùng lưới, lead liền bậc, `_P` lên `_MP`.
- Intro dài, bước 0: block I thế thấp, `_PP`.
- Intro dài, bước 1: iv hoặc IV rồi I, `_P`.
- Intro dài, bước 2: ii rồi V7, bè trong đi nửa cung, `_MP`.
- Intro dài, bước 3: I rồi V7, `_P`.
- Outro ngắn, bước 0: iv hoặc IV nửa đầu, I nửa sau, `_P`.
- Outro ngắn, bước 1: block I cả ô, `_PP`. Giữ thứ hoặc trưởng của điệu.
- Outro dài, bước 0: I rồi VI, hoặc IV, `_P`.
- Outro dài, bước 1: ii rồi V7, `_P`.
- Outro dài, bước 2: iv hoặc IV rồi I, `_PP`.
- Outro dài, bước 3: block I thế thấp, `_PP`.

**`choro`** — 4/4 nhanh, rally hoặc volatile, giai điệu chạy. Thân bài `_slot_dance` loại choro: bass root/fifth ở đầu mỗi nửa ô, bè trong ở móc kép 3, 6, 7 và 11, 14, 15, có accent ở nhát đảo. Approach nửa cung ở móc kép cuối khi root sau thấp hơn một quãng 5.

- Intro ngắn, bước 0: bass root/fifth ở móc đơn 0, 2, 4, 6. Bè trong trên móc kép ngay trước phách, `_P` lên `_MP`.
- Intro ngắn, bước 1: nửa đầu cell trên V7. Nửa sau bass approach hoặc một câu ngắn vào phách 1, `_MP`.
- Intro dài, bước 0: bass 0, 2, 4, 6, hợp âm có bậc 7 hoặc 6, `_P`.
- Intro dài, bước 1: lead đảo phách trên I rồi ii, `_MP`.
- Intro dài, bước 2: cell đầy trên V7, accent đảo phách, `_MP`.
- Intro dài, bước 3: câu chạy và bass approach, `_MF`.
- Outro ngắn, bước 0: cell trên V7, `_MP`.
- Outro ngắn, bước 1: một nhát đảo, rồi I staccato có accent ở phách 2.
- Outro dài, bước 0: cell trên I rồi ii, `_MP`.
- Outro dài, bước 1: cell trên V7, `_MP`.
- Outro dài, bước 2: bass đi xuống rồi đảo phách, `_P` lên `_MP`.
- Outro dài, bước 3: đảo phách rồi I staccato có accent.

**`polca`** — 6/8 nhanh, không calm, không phải đa số forte. Thân bài: bass ở móc kép 0 và 6, bè trong ở 2, 4, 8, 10. Trên móc đơn đó là bass 0 và 3, bè trong 1, 2, 4, 5.

- Intro ngắn, bước 0: bass root ở 0, fifth có nhấn nhẹ ở 3, bè trong ở 1, 2, 4, 5, `_P`.
- Intro ngắn, bước 1: cùng nền trên V7, hai móc đơn cuối lead lấy đà, `_MP`.
- Intro dài, bước 0: bass và bè trong trên I, `_P`.
- Intro dài, bước 1: lead nhảy quãng 3 trên I rồi IV, `_MP`.
- Intro dài, bước 2: nền trên V7, `_MP`.
- Intro dài, bước 3: lấy đà trên V7, `_MP` lên `_MF`.
- Outro ngắn, bước 0: polca trên V7, `_MP`.
- Outro ngắn, bước 1: hợp âm staccato ở móc đơn 0 và 3, nhát sau là I có accent.
- Outro dài, bước 0: polca trên IV, `_MP`.
- Outro dài, bước 1: polca trên V7, `_MP`.
- Outro dài, bước 2: I rồi V7, `_P` lên `_MP`.
- Outro dài, bước 3: hai hợp âm I staccato ở 0 và 3.

**`hemiola`** — 6/8 nhanh, forte là đa số. Thân bài đánh bass và bè trong ở móc đơn 0, 2, 4, accent ở 2 và 4, trong khi lead của điệu giữ phách 0 và 3.

- Intro ngắn, bước 0: bass và bè trong ở 0, 2, 4 trên I, accent ở 2 và 4. Lead giữ 0 và 3, `_MP`.
- Intro ngắn, bước 1: cùng lưới trên V7, `_MP` lên `_MF`.
- Intro dài, bước 0: 6/8 thuận, bass ở 0 và 3, trên I, `_P`.
- Intro dài, bước 1: bẻ sang 0, 2, 4 trên IV, `_MP`.
- Intro dài, bước 2: 0, 2, 4 trên V7, accent ở 2 và 4, `_MP`.
- Intro dài, bước 3: hemiola trên V7 vào thân bài, `_MF`.
- Outro ngắn, bước 0: 0, 2, 4 trên V7, `_MP`.
- Outro ngắn, bước 1: block I ở móc đơn 0, và ở 3 nếu ô còn chỗ, rồi ngân, `_P`.
- Outro dài, bước 0: hemiola trên IV, `_MP`.
- Outro dài, bước 1: hemiola trên V7, `_MP`.
- Outro dài, bước 2: trở lại 0 và 3, I rồi V7, `_P`.
- Outro dài, bước 3: block I ở phách 1, `_P`.

**`vals`** — chỉ ra từ `_contrast_pattern` khi primary là `polca` hoặc `hemiola` trên 6/8 nhanh có khung. Pattern đứng ở nhóm B. Đợt này không phát cửa này, mục 1.6. Kịch bản dưới đây chờ một form đặt `vals` kề pedal. Thân bài `_render_vals_bar`: bass root nửa phách ở beat 0, fifth ở beat 1.5, nốt đi qua có accent ở beat 2; bè trong ở móc đơn 1, 2, 4, 5.

- Intro ngắn, bước 0: bass I ở móc đơn 0, hợp âm ở 2 và 4, `_P`.
- Intro ngắn, bước 1: bass qua V7, lead một nét liền bậc, `_MP`.
- Intro dài, bước 0: arpeggio trên I, `_P`.
- Intro dài, bước 1: bass ở 0, hợp âm ở 2 và 4, trên I, `_P`.
- Intro dài, bước 2: cùng nhịp trên V7, nhấn móc đơn 4, `_MP`.
- Intro dài, bước 3: nét valse vào thân bài, `_MP`.
- Outro ngắn, bước 0: valse trên V7, `_P`.
- Outro ngắn, bước 1: bass I ở phách 1, hợp âm ở phách 2, rồi ngân, `_PP`.
- Outro dài, bước 0: valse trên iv hoặc IV, `_P`.
- Outro dài, bước 1: valse trên V7, `_P`.
- Outro dài, bước 2: lead về chủ âm, nền thưa, `_PP`.
- Outro dài, bước 3: bass I ở phách 1, hợp âm I ngân, `_PP`.

**`thumb_cantabile` của Barrios** — chỉ ra từ `_contrast_pattern`, đứng ở nhóm B. Đợt này không phát cửa này, mục 1.6. Kịch bản dưới đây chờ một form đặt pattern này kề pedal. Thân bài: giai điệu ở voice 3, cữ `48..64`; dyad ở `_thumb_offsets` (4/4 là 2 và 6, 6/8 là 2 và 5 hoặc 1, 2, 4, 5, 3/4 là 2 và 4), velocity khoảng `42..46`.

- Intro ngắn, bước 0: dyad ở phách yếu, `_PP`. Voice 3 một nốt ngân ở phách 1, trong cữ thumb, `_P`.
- Intro ngắn, bước 1: voice 3 hai nốt `V7 → I`, velocity viết `52 → 56`, một dyad giữa ô, vào cao độ thumb của thân bài.
- Intro dài, bước 0: dyad trên một bass buông, `_PP`.
- Intro dài, bước 1: voice 3 hai nốt trên I, `_P`.
- Intro dài, bước 2: voice 3 qua ii hoặc IV rồi V7, dyad thưa, `_P` lên `_MP`.
- Intro dài, bước 3: voice 3 liền bậc vào nốt đầu thân bài, `_MP`.
- Outro ngắn, bước 0: voice 3 về I, dyad cuối ở móc đơn 2, `_P`.
- Outro ngắn, bước 1: voice 3 ngân I một mình, `_PP`.
- Outro dài, bước 0: voice 3 qua IV rồi I, dyad thưa, `_P`.
- Outro dài, bước 1: qua V7, `_P`.
- Outro dài, bước 2: I, một nốt bè trong, `_PP`.
- Outro dài, bước 3: voice 3 giữ chủ âm, `_PP`.

### 6.4 Villa-Lobos

**`villa_pattern`** — 6/8, và 4/4 khi chưa khóa etude. Thân bài: bass root/fifth ở 0 và 4 (6/8 là 0 và 3), sóng bè trong ở móc đơn còn lại, accent tresillo `{0, 3, 6}` trên 4/4.

- Intro ngắn: `_villa_intro_short`. Bước 0 `_roll` trên I. Bước 1 `_stabs` rồi nhả về bass buông.
- Intro dài: `_villa_intro_long`. Bước 0 và 1 `_roll` với `shift` theo index. Bước 2 `_ascending`. Bước 3 block có accent rồi ngân.
- Outro ngắn, bước 0: `_ascending` trên I.
- Outro ngắn, bước 1: `_stabs` khi mood ô thân bài cuối là `rally`. Mood khác thì `_roll` về dây buông, `_P`.
- Outro dài, bước 0: `_roll`.
- Outro dài, bước 1: `_open_pedal`.
- Outro dài, bước 2: `_ascending`.
- Outro dài, bước 3: `_stabs` khi `rally`, còn lại `_bell_chord` không Picardy, `_P`. Stab `70 / 66 / 62` chỉ bật ở bước này, mục 4.5.

**`chord_melody`** — bpm từ 72 trở xuống, calm, hoặc piano là đa số. Thân bài: hợp âm khối trên `_chord_grid`, bè trong là màu `_COLOR_SUSPENDED` hoặc `_COLOR_TERTIAN` đi cùng lead qua `_block_tone`.

- Intro ngắn, bước 0: hai khối trên `[0, 4]` (6/8 thì `[0, 3]`), lead ở trên, bè trong là màu, `_P`.
- Intro ngắn, bước 1: hai khối qua V7, hoặc dịch một cung rồi về, lead liền bậc, `_MP`.
- Intro dài, bước 0: một khối I cả ô, thế thấp, `_PP` lên `_P`.
- Intro dài, bước 1: hai khối dịch song song trên `_chord_grid`, `_P`.
- Intro dài, bước 2: một khối mỗi nốt đen, vừa khít ô, `_MP`. Chương chậm guitar là 3/4, `epb = 6`, bpm 72: ba khối ở móc đơn 0, 2, 4. 4/4 mới có bốn khối ở 0, 2, 4, 6. Móc 6 không được viết trên 3/4.
- Intro dài, bước 3: hai khối V7 rồi I, `_P`.
- Outro ngắn, bước 0: hai khối chậm V7 rồi I, `_P`.
- Outro ngắn, bước 1: ba bè đánh I ở phách 1. Voice 2 dừng sau nửa ô. Bass và lead ngân hết ô, `_PP`.
- Outro dài, bước 0: khối IV rồi I, `_P`.
- Outro dài, bước 1: khối trên V7, `_P`.
- Outro dài, bước 2: khối I, bè trong nhả trước, `_PP`.
- Outro dài, bước 3: bass buông và lead, quãng 8 hoặc quãng 10, `_PP`.

**`thumb_cantabile` của Villa** — selloff. Pattern này mở được chương. Thân bài cùng lưới `_thumb_offsets`, voice 3 hát ở 64..72, dyad ở `42..46`.

- Intro ngắn, bước 0: bass buông ở phách 1. Từ phách 2 voice 3 đi lên từng bậc, `_P` lên `_MP`. Một hợp âm ở offset cuối của `_thumb_offsets`, `_PP`. Trên 3/4 offset đó là 4, không phải 6.
- Intro ngắn, bước 1: voice 3 ngân, dyad ở `_thumb_offsets`, vào câu thumb của thân bài. `selloff` với bpm từ 72 trở xuống là 3/4, offset là 2 và 4.
- Intro dài, bước 0: voice 3 ba nốt từ dây trầm đi lên, hai bè trên nghỉ, `_P` lên `_MP`.
- Intro dài, bước 1: voice 3 ngân nốt đỉnh, dyad ở phách yếu, `_PP`.
- Intro dài, bước 2: voice 3 qua iv rồi V7, đệm ở `_thumb_offsets`, `_MP`.
- Intro dài, bước 3: voice 3 vào đúng cao độ mở đầu thân bài, `_MP`.
- Outro ngắn, bước 0: voice 3 kết trên I, dyad lần cuối ở móc đơn 2, `_P`.
- Outro ngắn, bước 1: voice 3 giữ I cả ô, `_PP`.
- Outro dài, bước 0: voice 3 qua iv rồi I, đệm phách yếu, `_P`.
- Outro dài, bước 1: voice 3 trên V7 rồi I, một dyad ở móc đơn 2, `_PP`.
- Outro dài, bước 2: một harmonics hoặc dây buông cao trên voice 3 giữ I, `_PP`.
- Outro dài, bước 3: voice 3 một nốt trầm chủ âm, `_PP`.

**`etude1`** — 4/4, bpm trên 72, rally. Thân bài: một vòng 16 móc kép, bass root cả ô, bè trong theo `_ETUDE1_MIDDLE` và `_ETUDE1_ARC`, lead ở móc kép 7 và 9. `breathe` bỏ móc kép từ 12.

- Intro ngắn, bước 0: nửa đầu móc đơn trên dây buông I, `_P`. Nửa sau bè trong vào móc kép.
- Intro ngắn, bước 1: một vòng 16 móc kép trên I đứng. Hai nốt lead ở slot 7 và 9 là âm hợp âm chuẩn bị cho nốt đầu thân bài, `_P` lên `_MP`.
- Intro dài, bước 0: bass buông và bốn nốt arpeggio chậm, `_PP` lên `_P`.
- Intro dài, bước 1: một vòng etude trên I, `_P`.
- Intro dài, bước 2: một vòng ở thế tay kế, V7 trên pedal I, `_MP`.
- Intro dài, bước 3: một vòng về I, `breathe` ở bốn móc kép cuối, `_MP`.
- Outro ngắn, bước 0: một vòng trên I, `breathe`, nửa sau giảm `_MP` xuống `_P`.
- Outro ngắn, bước 1: bass ở phách 1, một nốt giữa ở phách 2, lead chủ âm từ phách 3 ngân hết ô, `_PP`.
- Outro dài, bước 0: một vòng dịch về I, `_MP`.
- Outro dài, bước 1: một vòng trên I với `breathe`, `_P`.
- Outro dài, bước 2: giãn móc kép thành móc đơn đi xuống, `_P` xuống `_PP`.
- Outro dài, bước 3: dây trầm và chủ âm ngân, `_PP`.

**`etude11`** — 4/4, bpm trên 72, volatile. Thân bài: mỗi nốt đen là một chùm 6. Bass và lead ở đầu phách, lead nhắc ở `+0.5`, bè trong ở slot 1, 2, 4, 5. Phách cuối của câu rời pattern có thể `drop_middle`.

- Intro ngắn, bước 0: voice 3 hai nốt chậm trên dây buông, `_P`.
- Intro ngắn, bước 1: nửa đầu một hợp âm chuẩn bị, `_MP`. Nửa sau hai vòm chùm 6 trên I.
- Intro dài, bước 0: giai điệu chậm trên hợp âm màu dây buông, `_PP`.
- Intro dài, bước 1: tiếp câu chậm, `_P`.
- Intro dài, bước 2: một vòm chùm 6 ở nửa đầu rồi ngân, `_MP`.
- Intro dài, bước 3: bốn vòm trên I, phách 4 bỏ bè trong, `_MP`.
- Outro ngắn, bước 0: hai vòm ở nửa đầu, nửa sau giãn thành móc đơn về I, `_MP` xuống `_P`.
- Outro ngắn, bước 1: hợp âm I, nhấn bằng velocity `_MP`, bass ngân hết ô. Không `staccato`, không đi qua `villa_stab`.
- Outro dài, bước 0: bốn vòm, `_MP` xuống `_P`.
- Outro dài, bước 1: hai vòm đầu ô, nửa sau trở lại câu chậm, `_P`.
- Outro dài, bước 2: voice 3 bước xuống chủ âm, `_P` xuống `_PP`.
- Outro dài, bước 3: hợp âm I nhấn trong velocity đã viết, rồi ngân, `_PP`.

### 6.5 Brouwer

**`noviembre`** — calm. Thân bài: pulse bass ở 0 và 4 (6/8 là 0 và 3), pickup cuối ô được `_soften_attack`, sóng màu ở 1, 2, 3, 5, 6.

- Intro ngắn, bước 0: `_deep_open` cả ô, `_PP`.
- Intro ngắn, bước 1: `_color_roll` trên sus2, `_P`.
- Intro dài, bước 0: một nốt chuông, `_PP`.
- Intro dài, bước 1: `_cantabile`, `_P`.
- Intro dài, bước 2: `_color_roll`, `_P`.
- Intro dài, bước 3: `_settled` trên I, `_MP`.
- Outro ngắn, bước 0: `_sparse` trên I, `_P`.
- Outro ngắn, bước 1: `_bell_chord`, `_PP`. Picardy giữ cho pattern này.
- Outro dài, bước 0: `_thin_roll`, `_PP`.
- Outro dài, bước 1: `_tonic_steps`, `_P`.
- Outro dài, bước 2: `_beat_two_hang`, `_P`.
- Outro dài, bước 3: `_bell_chord`, `_PP`.

**`brouwer_etude`** — rally và các mood còn lại sau khi calm, selloff, volatile đã chọn pattern khác. Thân bài là `_etude_cells`: 4/4 là `(0, 3)`, `(3, 3)`, `(6, 2)` có bước ở cell cuối; 6/8 là `(0, 2)`, `(2, 3)`, `(5, 1)`; 3/4 là `(0, 3)`, `(3, 3)`. Bè trong đứng ở móc đơn bass không chiếm, ưu tiên dây buông.

- Intro ngắn, bước 0: voice 3 chơi tumbao một mình trên I, `_P`. Một nốt dây buông ở voice 2, móc đơn 2.
- Intro ngắn, bước 1: bass và bè trong đủ cell, sus2 xen dây buông, `_MP`. Móc đơn cuối bass dùng `_toward_next` khi root đổi.
- Intro dài, bước 0: bass ở 0 và 3, `_PP` lên `_P`.
- Intro dài, bước 1: đủ ba điểm tumbao, hai nốt dây buông, `_P`.
- Intro dài, bước 2: tumbao đủ hai bè, hợp âm màu cách một cung rồi về I, `_MP`.
- Intro dài, bước 3: tumbao trên I, lead vào ở nửa sau, `_MP`.
- Outro ngắn, bước 0: tumbao, bè trong chỉ còn móc đơn 1 và 4, `_MP` xuống `_P`.
- Outro ngắn, bước 1: một hợp âm sus2 hoặc add9 từ phách 1 hết ô, `_P`.
- Outro dài, bước 0: một ô tumbao đủ, `_P`.
- Outro dài, bước 1: bass còn 0 và 3, hai nốt dây buông, `_P`.
- Outro dài, bước 2: `_tonic_steps` dưới dây buông, `_PP`.
- Outro dài, bước 3: hợp âm sus2 ngân, `_PP`.

**`sarabande`** — selloff hoặc bpm từ 72 trở xuống. Thân bài nhấn sus2 ở phách 2 (`_sarabande_points`: eighth 2, riêng 6/8 là 3). Nửa sau có thể `_modal_figure`, mỗi bước từ 1 đến 2 semitone.

- Intro ngắn, bước 0: `_beat_two_hang` trên `_sus2`. Phách 1 bass `_P`, phách 2 hợp âm `accent` ở `_MP`, ngân hết ô.
- Intro ngắn, bước 1: trọng phách 2 trên màu thấp hơn một cung. Nửa sau lead ba hoặc bốn nốt, mỗi bước tối đa 2 semitone, `_MP`.
- Intro dài, bước 0: bass buông ở phách 1, sus2 ở phách 2, `_PP` lên `_P`.
- Intro dài, bước 1: trọng phách 2 trên màu thứ hai, `_P`.
- Intro dài, bước 2: một đoạn swarm ngắn sau phách 2, `_MP`.
- Intro dài, bước 3: phách 2 nhẹ hơn, lead liền bậc vào thân bài, `_P`.
- Outro ngắn, bước 0: `_beat_two_hang` trên sus2, `_P`.
- Outro ngắn, bước 1: quãng 5 trống, root ở voice 3 và fifth ở voice 1 hoặc 2, `_PP`.
- Outro dài, bước 0: phách 2 rồi ba nốt đi xuống, `_P`.
- Outro dài, bước 1: `_tonic_steps`, `_P`.
- Outro dài, bước 2: `_beat_two_hang`, `_PP`.
- Outro dài, bước 3: quãng 5 buông trầm, `_PP`.

**`elogio_pizz`** — volatile. Thân bài: staccato ở `_elogio_offsets` (4/4 là 0, 2, 3, 5, 6), slap staccato và accent ở móc đơn 3.

- Intro ngắn, bước 0: `_edge_stab`, hợp âm sus2 staccato có accent ở 0, rồi bass buông. Thêm một slap ở móc đơn 3.
- Intro ngắn, bước 1: `_edge_run`, bass dừng giữa ô, bốn móc đơn staccato đi lên.
- Intro dài, bước 0: `_deep_open` staccato có accent, `_MF`.
- Intro dài, bước 1: `_hesitant_bass`, hai nốt bass cách một semitone, `_P`.
- Intro dài, bước 2: `_parallel_stabs` ở 1, 3, 6, `_MP`.
- Intro dài, bước 3: `_accel`, từ nốt dài vào móc đơn, `_MP` lên `_MF`.
- Outro ngắn, bước 0: `_syncopated_blocks` ở 1 và 5, `_MP`.
- Outro ngắn, bước 1: `_stab_and_ring`, hai cú staccato có accent ở 0 và 2, rồi nghỉ.
- Outro dài, bước 0: `_sparse`, `_P`.
- Outro dài, bước 1: `_ascending`, `_MP`.
- Outro dài, bước 2: `_wide_chord`, `_P`.
- Outro dài, bước 3: một bass buông staccato có accent ở phách 1, `_MF`, rồi nghỉ.

---

## 7. Việc đợt code đụng tới, và việc để yên

Đợt code đụng tới:

- Chữ ký `render_intro` / `render_outro`, và pattern đi qua `_gesture`, `_compressed`, `_gesture_body`. Mục 4.1.
- Bỏ `_plant_pickup` trên ô pedal, mục 4.3.
- Điều kiện `villa_stab`, mục 4.5. `villa_pattern` ở mood `volatile` mất stab.
- Profile ô pedal theo mục 4.4: `thumb_cantabile`, `elegiaque`, `barrios_dance` cho choro. Trần voice 3 của hai cửa thumb.
- Lưới móc kép hoặc chùm 6 đúng các pattern đã nêu ở mục 4.4.
- Test đang khóa cửa theo tác gia. `test_villa_dialect.py` có `test_bach_dance_frames_take_an_upbeat_into_an_authentic_cadence` và `test_bach_polyphonic_frames_expose_a_subject_and_a_picardy_third`. `test_sonify_guitar.py` có `test_composer_intro_and_outro_frames_for_two_and_four_bars` và `test_brouwer_frames_for_lyric_and_edge_modes`. Assertion `frame_roles(6) == [0, 0, 1, 2, 2, 3]` giữ nguyên.

Để yên:

- Không thêm pattern thân bài thứ 29. Pedal vẫn là đường khung, không phải một hàng trong `PROFILES`.
- Không vẽ cửa ở biên A|B. Kịch bản `vals` và thumb Barrios không được gọi trong đợt này, mục 1.6.
- Không đổi công thức `fit_intro` / `fit_outro`, sàn, trần, hay ba số stab.
- Không tách bản ngắn và bản dài thành hai loại nhạc.
