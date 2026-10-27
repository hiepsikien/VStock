# Intro và outro guitar: tình trạng hiện có và cửa riêng cho từng pattern

> **Phạm vi**: khung ở `backend/app/sonify/guitar_frame.py`, 28 pattern thân bài trong `PROFILES` của `backend/app/sonify/guitar_wave.py`.
> **Mục tiêu**: mỗi pattern chính có một loại intro và một loại outro. Short và long vẫn là hai độ dài của kịch bản đó.

Tài liệu này ghi lại khung đang chạy và đề xuất cửa mới. Chưa đổi code phát nhạc.

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

`brouwer_etude` ở rally đi cửa trữ tình. Cửa edge chỉ bật khi character cả chương là `volatile` hoặc `selloff`, tức là lúc thân bài đã là `elogio_pizz` hoặc `sarabande`.

### 1.5 Bach — hai cửa theo nhịp và character

Pattern: `bach_sarabande`, `bach_gavotte`, `bach_bourree`, `bach_fuga`, `bach_gigue`, `bach_chaconne`.

- **Vũ điệu** (Bourrée, Gavotte, Gigue bị gộp): intro ngắn là anacrusis I rồi chạy V7. Intro dài là pickup staccato, tetrachord bước xuống, mordent, scale lấy đà. Outro ngắn là nửa kết rồi block I. Outro dài là tetrachord, flourish V7, mordent, block I.
- **Phức điệu** (Fuga, Sarabande, Chaconne bị gộp): intro ngắn là arpeggio pedal rồi hàng xóm trên V7. Intro dài là subject, answer, hội tụ về V7, block I. Outro ngắn là I thưa rồi Picardy. Outro dài là pedal V7, pedal I, arpeggiato I+, Picardy.

`_bach_dance` không đọc pattern. Sarabande 3/4, bpm trên 72, character calm vẫn nhận cửa vũ điệu trong khi `_bach_primary` chọn `bach_sarabande`.

### 1.6 Pattern nào thực sự mở hoặc kết một chương

Trên đường framed, intro nghe pattern ô thân bài **đầu**, outro nghe pattern ô thân bài **cuối**. Hai pattern Barrios không bao giờ là pattern đó:

- `vals` chỉ là tương phản của polca / hemiola.
- `thumb_cantabile` của Barrios chỉ là tương phản khi bpm dưới 90 hoặc ở cầu.

26 pattern còn lại đều có lúc đứng đầu hoặc đứng cuối thân bài. Bộ chọn nằm ở `_dominant_pattern` trong `guitar_patterns.py`, với nhánh riêng trong `guitar_bach.py`, `guitar_sor.py`, `guitar_barrios.py`, `guitar_brouwer.py`.

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

1. Intro đọc pattern của ô thân bài đầu. Outro đọc pattern của ô thân bài cuối. Pattern lấy qua `_bar_pattern` của ô thân bài kề vùng pedal.
2. Khóa là `(ensemble, pattern)`, không chỉ `ensemble`.
3. Mỗi pattern có một kịch bản ngắn (bước 0–1) và một kịch bản dài (bước 0–3). `frame_roles` và `_compressed` giữ nguyên.
4. Bảy kịch bản đang có được **giao về một pattern**, không xóa và không dùng chung trong tác gia nữa.
5. `vals` và `thumb_cantabile` của Barrios vẫn có cửa trong bảng, để đoạn B có pickup sau này. Trên form hiện tại hai cửa đó không kêu, vì intro và outro bám pattern A.
6. Không đổi `fit_intro`, `fit_outro`, sàn, trần, hay stab gán sau bộ lọc (`70 / 66 / 62`).

Picardy chỉ giữ ở các cửa đã dùng nó với chủ đích: `preludio`, `noviembre`, `bach_fuga`. Galop, choro, vals, sarabande minor không kết bằng chuông Picardy.

---

## 4. Bảy kịch bản giữ lại, mỗi cái một pattern

| Pattern | Cửa được giao | Pattern cùng tác gia không dùng lại cửa này |
|---|---|---|
| `mozart_var` | Intro Op. 9 (chấm dôi Pháp, chạy về V7). Outro là turn trên V rồi I, sáng hơn Elegiaque | `study` nhận cadence V–I hiện tại. Bốn pattern classic còn lại viết cửa mới |
| `study` | Outro ngắn/dài V gọn → block I đang có. Intro mới là arpeggio I tĩnh rồi một mảnh scale | Op. 9 về `mozart_var` |
| `preludio` | Chuông hòa âm, arpeggio đi lên, outro thưa rồi chuông Picardy | Bảy pattern Barrios còn lại |
| `villa_pattern` | Roll dây buông và stab intro. Outro roll thưa về dây buông. Stab sáng cuối outro chỉ còn ở rally của pattern này | `chord_melody`, `thumb_cantabile`, `etude1`, `etude11` |
| `noviembre` | Chuông một nốt, cantabile, color roll, I ổn định. Outro roll mỏng, bước chủ, phách 2 treo, chuông mềm | `sarabande`, `brouwer_etude` |
| `elogio_pizz` | Cửa edge: stab, bass ngập ngừng, stab song song, dồn. Outro khối đảo phách, stab rồi ngân | Không gắn edge theo character cả chương nữa |
| `bach_bourree` | Anacrusis: bass I phách 1, ba móc đơn, rồi V7. Outro nửa kết → block I | `bach_gavotte`, `bach_gigue` |
| `bach_fuga` | Subject đơn âm, answer ở quãng 5 dưới. Outro là stretto ngắn rồi I hoặc Picardy | `bach_sarabande`, `bach_chaconne`. Pedal và arpeggiato của outro phức điệu dài chuyển sang Chaconne |

Tám dòng vì Study và Mozart chia đôi một cặp intro/outro đang dính liền. Đếm theo pattern thì tám pattern giữ một phần cửa cũ. Hai mươi pattern còn lại viết cả intro lẫn outro.

---

## 5. Cửa mới theo pattern

Mỗi mục dưới là một loại. Bản ngắn là hai ô đầu và cuối của ý đó. Bản dài thêm hai ô giữa. Ô một ô vẫn cắt đôi bản ngắn.

### 5.1 Bach

**`bach_gavotte`** — 4/4, calm, bpm > 72. Đang dùng cửa Bourrée.

- Intro: lấy đà đúng nửa ô, chỗ Gavotte vào giữa nhịp. Hai nốt pickup, không ba móc đơn của Bourrée.
- Outro: hợp âm cuối rơi giữa nhịp, rồi một ô I đầy mới khép.

**`bach_gigue`** — 6/8, bpm > 72, không volatile/selloff. Đang dùng cửa Bourrée.

- Intro: móc đơn liên tục trên nhịp kép, chạy vào thân bài. Không chấm dôi Pháp, không pickup Bourrée.
- Outro: flourish trên V7 rồi I. `_bach_dominant_flourish` đang nằm trong outro dài của cả nhóm vũ điệu; chuyển về riêng Gigue.

**`bach_sarabande`** — 3/4, hoặc bpm ≤ 72 khi không phải chaconne. Bản chậm đang dùng cửa phức điệu; bản 3/4 nhanh và calm đang bị kéo sang vũ điệu.

- Intro: nhịp Sarabande, trọng phách 2. Không xướng subject.
- Outro: phách 2 ngân, rồi I. Điệu minor kết hợp âm minor.

**`bach_chaconne`** — selloff, hoặc 3/4 selloff với biên độ đủ lớn. Đang dùng cửa phức điệu. Tetrachord bước xuống lại đang nằm trong intro vũ điệu dài.

- Intro: ground bass bước xuống một mình, rồi bariolage mới vào. Tetrachord rời khỏi cửa Bourrée.
- Outro: ground bass lần cuối, arpeggiato chậm (`_bach_arpeggiato` đang là bước 2 của outro phức điệu), rồi I.

### 5.2 Sor (`ensemble = "classic"`)

**`study`** — mặc định, và rally hẹp hoặc minor. Đang mở bằng Op. 9.

- Intro: arpeggio I tĩnh, rồi một mảnh scale đúng ô study nối vào thân bài.
- Outro: giữ V gọn → I như mục 4.

**`cantabile`** — calm, bpm > 72.

- Intro: một bè hát trên bass nghỉ. Quãng 6 đi cùng (`_sor_lyric_walk` / `_cantabile`). Không chấm dôi.
- Outro: appoggiatura thở vào I nhẹ. Bè trong ngân, không chặn hợp âm.

**`elegiaque`** — selloff hoặc bpm ≤ 72.

- Intro: bass lament bước xuống dưới giai điệu ngân, pp.
- Outro: dây buông ngân. Không V–I sáng của Study.

**`galop`** — rally rộng, trưởng, biên độ từ 1,2%.

- Intro: bass galop hai điểm trong ô (`_galop_bass_points`), cộng một lấy đà ngắn.
- Outro: hai hợp âm staccato rồi tonic chốt. Không block ngân dài.

### 5.3 Barrios

**`tremolo`** — finale, selloff/volatile ở moderato, hoặc nhiều nốt giữ.

- Intro: một nốt giai điệu được đặt trước. Nửa cuối ô intro cuối mới bắt a-m-i, để thân bài không khai sinh tremolo từ im lặng.
- Outro: tremolo thưa còn một ngón, rồi nốt giai điệu ngân. Không chuông.

**`andante`** — bpm dưới 90.

- Intro: hợp âm thánh ca trên lưới Andante, phách 1 và 3 (`_andante_grid`). Không chuông.
- Outro: hai hợp âm trắng, hợp âm cuối giữ. Không Picardy.

**`choro`** — 1D volatile mà giai điệu chạy, hoặc 4/4 nhanh rally/volatile.

- Intro: ô đảo phách, bass ăn trước phách 2. Một cell choro.
- Outro: nhấn đảo phách rồi stab I.

**`polca`** — 6/8 nhanh, không calm, không phải forte-majority.

- Intro: ô-phách polca, nhẹ hơn choro.
- Outro: hai cadence staccato.

**`hemiola`** — 6/8 nhanh, forte là đa số.

- Intro: hai ô 3 chống 2, để thân bài không phải khai sinh hemiola.
- Outro: hemiola đổ về nhịp thật. Hợp âm cuối đúng phách 1.

**`vals`** — chỉ trio. Cửa chỉ cần khi viết pickup vào đoạn B.

- Intro: bass valse phách 1, hợp âm phách 2 và 3.
- Outro: cadence valse, bass octave trên phách 1. Không tremolo, không chuông.

**`thumb_cantabile`** — chỉ tương phản khi bpm dưới 90 hoặc ở cầu.

- Intro: giai điệu ở ngón cái, bè trên là pedal mỏng.
- Outro: ngón cái hát nốt cuối một mình. Bè trên rời từng tiếng.

### 5.4 Villa-Lobos

**`chord_melody`** — bpm ≤ 72, calm, hoặc piano là đa số.

- Intro: một hợp âm khối mỗi ô, giai điệu nằm trên. Không roll.
- Outro: khối cuối giữ. Bè trong nhả trước, đúng cách kết Prélude No. 1.

**`thumb_cantabile`** — selloff. Pattern này có mở chương, khác thumb của Barrios.

- Intro: ngón cái hát, một hợp âm trên phách 1.
- Outro: ngón cái một mình trên I.

**`etude1`** — 4/4, bpm > 72, rally.

- Intro: đúng cell arpeggio Etude 1 trên một hợp âm đứng, trước khi giai điệu giá vào.
- Outro: arpeggio thu về hai dây ngoài và dừng trên I.

**`etude11`** — 4/4, bpm > 72, volatile.

- Intro: một lần cell hoa mỹ Etude 11, rồi pattern khóa.
- Outro: hoa mỹ giải xuống I, nhấn rồi ngân. Không chuông của chord melody, không mượn stab sáng của `villa_pattern`.

### 5.5 Brouwer

**`sarabande`** — selloff hoặc bpm ≤ 72. Đang dùng cửa trữ tình của Noviembre.

- Intro: trọng phách 2, màu sus2 (`_sus2`). Chậm. Không chuông Noviembre.
- Outro: phách 2 treo, rồi quãng 5 buông trầm. Không Picardy.

**`brouwer_etude`** — rally và các mood còn lại. Rally hiện đi cửa trữ tình.

- Intro: cell tumbao nhỏ, rồi khóa máy. Không stab của Elogio.
- Outro: máy chậm lại thành một hợp âm giữ.

---

## 6. Việc không làm trong đợt này

- Không thêm pattern thân bài thứ 29. Pedal vẫn là đường khung, không phải một hàng trong `PROFILES`.
- Không vẽ cửa riêng ở biên trio, trừ khi làm tiếp pickup cho `vals` và thumb Barrios.
- Không đổi đường tâm intro/outro, sàn của ô thân bài đang nối, hay cách kẹp trần.
- Không tách short và long thành hai loại nhạc. Chúng vẫn là một loại, hai độ dài.
