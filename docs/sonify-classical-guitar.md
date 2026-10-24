# Guitar cổ điển: một nhạc cụ, ba bè, năm đại sư

> **Trạng thái** (2026-10-24): **Đã hoàn thành toàn bộ Phase 1–3, kiến trúc Macro "One-Pattern Flow" (`_assign_macro`), khung Intro/Outro riêng theo tác gia (`guitar_frame.py`), và mở rộng đủ 5 Đại Sư (`Bach | Sor | Barrios | Lobos | Brouwer`).**
>
> - **Đường chạy thực tế (`_framed(ctx) == True` — mọi bài `1D`, `1W`, `1M`, `3M`, `1Y` do `render()` tạo)**:
>   - Đi qua **bộ chọn Macro (`_assign_macro` / `_dominant_pattern` / `_contrast_pattern`)**: bản ngắn `1D` khóa **1 pattern chủ đạo xuyên suốt thân bài** (Monothematic); các chương dài có `trio`/`bridge` đi theo cấu trúc **A–B–A** (phần A giữ 1 pattern chính, phần B chuyển sang 1 pattern tương phản rồi quay về A); bản tuần `1W` khóa 1 pattern mỗi phiên.
>   - Vùng `intro`/`warmup` và `cooldown`/`outro` được thay bằng **khung Intro/Outro 2 ô & 4 ô riêng của từng tác gia** (`guitar_frame.py`), nối vào thân bài bằng nốt Bass pickup và giảm tốc kết cấu nửa ô cuối (`_relax_texture` / `_smooth_boundaries`).
>   - Với Barrios ở bài có khung (`_catedral_preludio(ctx)`), pattern `preludio` chạy đúng lưới **16 móc kép đan xen nguyên bản của *La Catedral — Preludio Saudade*** (mỗi khung 2 phách gồm 2 nốt giai điệu *canto* ở móc kép `0` và `6` đan với sóng chữ V 6 móc kép `1, 2, 3, 4, 5, 7` ở bè Trung, tắt chèn chuông/scale đè lên *canto*).
> - **Đường chạy unit-test không khung (`_framed(ctx) == False` — các fixture truyền câu rời không có section `intro`/`outro`)**:
>   - Giữ nguyên bộ chọn từng câu (`_select_body`), `_taper`, `_transitions` và bản `preludio` móc đơn có chuông của Phase 1–3 để bảo toàn toàn bộ các unit test cấp câu.
>
> **Liên kết**: [`docs/sonify-explain.md`](./sonify-explain.md), [`docs/sonify-instrument-sets.md`](./sonify-instrument-sets.md), [`docs/sonify-long-form.md`](./sonify-long-form.md), [`docs/sonify-guitar-improvement-plan.md`](./sonify-guitar-improvement-plan.md), [`docs/sonify-la-catedral-preludio.md`](./sonify-la-catedral-preludio.md), [`docs/sonify-guitar-bach-plan.md`](./sonify-guitar-bach-plan.md).

---

## Đã hoàn thành trong code

Khung đang chạy trong `backend/app/sonify/guitar.py`, `backend/app/sonify/guitar_patterns.py`, `backend/app/sonify/guitar_frame.py` và `backend/app/sonify/harmony.py`:

- Variant `guitar`, một part nylon `Acoustic Nylon`, ba voice trên một khuông, `<backup>` giữa các voice, `octave-change -1` cùng `written_shift +12`.
- **UI & 5 Đại Sư (`ENSEMBLE_ROWS.guitar`)**: **Bach** (`bach`, 96 BPM), **Sor** (`classic`, 88 BPM), **Barrios** (`barrios`, 120 BPM), **Lobos** (`villa`, 100 BPM), **Brouwer** (`brouwer`, 108 BPM). Hàng guitar của minimalist là **Guitar thép**.
- **5 Dialect hòa âm riêng biệt (`harmony.py`)**:
  - `BachDialect` (`bach`): Vòng quãng 5 liên hoàn Trưởng/Thứ, chuỗi Át phụ & Giảm bảy, mở cửa `Bb / Bb7 (bVII → III)` và `D7 (V7/V)` ở giọng Thứ.
  - `SorDialect` (`classic` khi `variant="guitar"`): Hòa âm Cổ điển thuần khiết (hợp âm ba, `G7`, `Dm7`, Át phụ `D7, E7, A7, C7, F#dim7`; cấm `Cmaj7, Fmaj7, Am7, Em7, Cm7, Fm7, Ebmaj7, Abmaj7`).
  - `BarriosDialect` (`barrios`): Vòng quãng 5 thứ (`Bb, Bb7, D7`), sext tăng Đức `Ab+6` một ô trước `G/G7`, và chuỗi Át trưởng `E7 → A7 → D7 → G7`.
  - `VillaDialect` (`villa`): Hợp âm treo `sus2, sus4, 7sus4`, `add9 / madd9`, và trượt song song `Csus2 → Bbsus2`, `Fsus2 → Ebsus2`.
  - `BrouwerDialect` (`brouwer`): Kết hợp trượt hợp âm treo `sus2/add9` (*Estudio No. 6*) với vòng modal Afro-Cuban `Cm ↔ Bb/Bb7 → Eb/Ebmaj7 → G7sus4 → Cm` (*Un Día de Noviembre*).
- **Chương dưới 90 BPM của Barrios**: giữ nguyên BPM chậm (`60, 66, 72`), hát thánh ca **`andante`** (*Andante Religioso*) ở phần A và **`thumb_cantabile`** (*Julia Florida*) ở đoạn giữa `bridge` (không tremolo, không kéo nhanh tempo).

## Lịch sử 3 Phase nền tảng (áp dụng trực tiếp cho bộ chọn cấp câu `_select_body`)

### Phase 1 — Bộ chọn, và hai cách hát

Nghe được: câu ngân từ 90 BPM là tremolo; chương dưới 90 của Barrios và các câu vai hát ở bước 3 là thánh ca của nhà đó; câu mở của chương từ 90 BPM và các câu còn lại vẫn là arpeggio đang có. Chưa có điệu Nam Mỹ, chưa có dialect Barrios, chưa có scale.

- Hàm chọn pattern theo thứ tự mục 3, và quy tắc khớp nối / điểm thở ở mục 3.2. Cửa tempo lọc trước sở thích của nhà.
- Tremolo chỉ khi được chọn. Giữ nguyên lưới, lực, và việc ngón cái không nhường phách. Không viết lại thành phách chấm ở 6/8. Tắt tremolo ở hai phách đen cuối của câu đóng (`phrase.closes`) hoặc của câu tremolo ngay trước khi đổi sang pattern khác (khi câu dài từ bốn phách đen trở lên, phần trước còn ít nhất hai phách tremolo).
- Thánh ca: Andante của Barrios, chord-melody của Villa, Élégiaque của Sor, đúng mục 6.
- Sau hai câu tremolo liên tiếp, câu kế là thánh ca. Luật này chỉ chạy khi tremolo đang hợp lệ.
- Câu mở của chương từ 90 BPM và câu chạy không rơi vào thánh ca vẫn gọi arpeggio hiện tại. Pattern `preludio` (arpeggio khai của *La Catedral* kèm chuông), pattern `villa_pattern` (*Étude No. 1*), và các lớp phủ/biến tấu cấp câu để Phase 3.

### Phase 2 — Dialect Barrios và điệu nhanh

Nghe được: thứ đi được vòng quãng 5 trên nốt thuộc thang; trưởng đi được chuỗi át bảy khi giá ngồi trên Đô, La hoặc Rê; câu nốt chạy trên 100 BPM ở 4/4 hoặc 6/8 là choro hoặc polca. Câu đang ngân vẫn tremolo.

- Đầu phase, đọc tổng phổ và khóa số móc mục 9.1 và 9.2. Lệch thì sửa bảng trong file này trước khi viết renderer.
- `BarriosDialect`, bốn hợp âm thứ, các cạnh, `quality_group` của `+6`, và luật một ô `"augmented-sixth"` trong `form.py`. Không sửa `minor_bias`.
- Điệu chỉ khi bộ chọn đã trả `dance`. Hemiola là bản to của polca, không phải cách thay tremolo.

### Phase 3 — Các pattern đặc trưng còn lại và lớp phủ cấp câu (Scale, Grand Solo)

Nghe được: mở bài Barrios là pattern `preludio` có chuông; vòng `villa_pattern` tách khỏi `study` đều của Sor; Sor `calm` hát song thanh quãng 3/6 (`cantabile`); đoạn `section.trio` của Villa và Barrios hát giai điệu ngón cái ở bè Trầm (`thumb_cantabile` kiểu *Prélude No. 1* / *Julia Florida*) hoặc *Vals* Nam Mỹ (`vals` ở scherzo 6/8); đỉnh câu có đoạn scale rơi đúng nốt giá; Grand Solo phủ biến tấu dày lên trên pattern `study` khi câu lặp.

- Tách họ Arpeggio thành ba pattern riêng: `study` (Sor), `villa_pattern` (vòng *Étude No. 1*, campanella), và `preludio` (pattern arpeggio khai *La Catedral* với bass mỗi hai ô và chuông).
- Bổ sung ba pattern đặc trưng vào họ Thánh ca và Điệu:
  1. **`thumb_cantabile` (Giai điệu ngón cái ở bè Trầm — Villa *Prélude No. 1* / Barrios *Julia Florida*)**: đảo vai bè ở câu giữa (`section.trio`) hoặc câu nghỉ, ngón cái `p` hát đường giá ở vùng Cello (C3–E4), bè trên chập hợp âm hai nốt ở phách yếu.
  2. **`cantabile` (Song thanh quãng 3 / quãng 6 — Sor *Op. 6 No. 10*, *Op. 31 No. 21*)**: bè Trung đi song song quãng 3 hoặc quãng 6 thuận thang ngay dưới bè Cao trên nền bass gốc đầu ô khi Sor ở `calm`.
  3. **`vals` (Valse Venezolano / Vals Criollo — Barrios *Vals Op. 8 No. 3 & 4*)**: điệu waltz Nam Mỹ đan nhịp 6/8–3/4 (bass ở móc đơn `0, 3, 4` kèm hợp âm phách yếu) cho câu chạy ở `section.trio` của chương 6/8 (`120, 108 BPM`).
- Các lớp phủ và biến tấu cấp câu (không phải họ pattern tay phải mới): Scale phủ bè Cao (grammar một, giá trị nốt theo tempo, đệm phía dưới vẫn của pattern chủ); Grand Solo phủ lên pattern `study` của Sor (tăng bậc figuration theo lần lặp cùng họ câu, fanfare khối đầu section band `f`, caesura trước câu đỉnh, và gọi scale lên đỉnh).
- `assert_playable` theo profile, mô hình dây và phím. Trần ba bè giữ nguyên; ngoại lệ tremolo đã nghe (gốc và quãng 5 cùng voice Trầm) không bị siết lại.

---

## 1. Ba tầng và lớp phủ cấp câu

Người nghe vẫn chọn một nhà: `classic` (Sor), `villa`, `barrios`. Bên trong có ba tầng tách nhau, cộng các thủ pháp phủ cấp câu ở Phase 3.

**Dialect hòa âm** chọn hợp âm. Sor ở catalog chung. Villa có sus, add9 và hai hợp âm trượt. Barrios, từ Phase 2, có vòng quãng 5 thứ và chuỗi át trưởng. Dialect không biết tremolo hay choro.

**Pattern** là cách tay phải dệt ba bè trong phạm vi một ô nhịp. Mỗi pattern khai cửa tempo, meter được đứng, bè nào hát, bè nào giữ nhịp, và cách band `p–f` làm nó thưa hay dày. Band đổi mật độ trong pattern. Band không đổi họ pattern. Các đoạn hợp âm của Villa (`chord_melody`), `andante` của Barrios, khung hành khúc chấm dôi `elegiaque` của Sor, và `preludio` của *La Catedral* đều là các pattern thật sự ở tầng này.

**Palette** là danh sách pattern riêng của từng nhà soạn nhạc, cộng thứ tự ưu tiên khi nhiều pattern cùng hợp lệ. Bộ chọn chỉ được rút pattern từ palette của nhà đang chọn (lọc cửa tempo và meter trước, rồi mới xét thứ tự):

| Nhà soạn nhạc (`ensemble`) | Phong cách & Thẩm mỹ | Palette Pattern của riêng nhà đó | Lớp phủ & Biến tấu cấp câu (Phase 3) |
|---|---|---|---|
| **Sor (`classic`)** | Cổ điển châu Âu (cân đối, rõ câu cú, đối vị hai bè, hành khúc bi tráng) | • `study` (Arpeggio cổ điển đều)<br>• `elegiaque` (Hành khúc tang chấm dôi + bass lament)<br>• `cantabile` *(Phase 3)* (Song thanh quãng 3 / quãng 6 kiểu *Op. 6 No. 10*) | **`Grand Solo`** (Biến tấu dày dần `level 0→1→2` trên nền `study`, khối fanfare đầu đoạn, caesura) + **`Scale`** |
| **Villa-Lobos (`villa`)** | Hiện đại Brazil (cuộn sóng, hợp âm khối dồn dập, giai điệu dây trầm) | • `villa_pattern` (Arpeggio cuộn *Étude No. 1*, ngân chồng campanella khác dây ở Phase 3, nhấn tresillo 3+3+2)<br>• `chord_melody` (Khối 3 nốt hát *Étude No. 11*)<br>• `thumb_cantabile` *(Phase 3)* (Giai điệu ngón cái `p` vùng Cello *Prélude No. 1*) | **`Scale`** (*Étude No. 7*) |
| **Barrios (`barrios`)** | Lãng mạn muộn Nam Mỹ (nhà thờ, tremolo ngân liền, điệu nhảy dân gian) | • `preludio` (*La Catedral* — bass mỗi 2 ô + chuông)<br>• `tremolo` (`p–a–m–i` ngân liền)<br>• `andante` (Khối hợp âm nhà thờ *Andante Religioso*)<br>• `choro` (4/4), `polca` & `hemiola` (6/8), `vals` (6/8 trio, *Phase 3*)<br>• `thumb_cantabile` *(Phase 3)* (*Julia Florida*) | **`Scale` / `Perpetual`** (*Allegro Solemne*) |

**Lớp phủ và biến tấu cấp câu (Phrase Overlays / Modifiers — Phase 3)** như **Scale** hay **Grand Solo** không phải là một pattern tay phải độc lập trong ô nhịp, mà là quy tắc trang trí/biến tấu đặt lên trên pattern chủ của câu đó (Scale phủ lên bè Cao ở đỉnh/cuối câu; Grand Solo tăng bậc dày của pattern `study`, điểm khối fanfare đầu section và ngắt caesura).

Một chương có một BPM và một meter. Pattern nằm ngoài cửa thì không phải ứng viên. Không nâng tempo chương chậm để tremolo hợp lệ.

## 2. Năm họ

Một phách trong tài liệu này là một nốt đen: hai móc đơn, hoặc bốn móc kép.

| Họ | Cửa | Bè hát | Bè nhịp | Các pattern và phạm vi dùng chung |
|---|---|---|---|---|
| Arpeggio | Mọi tempo trên bản đồ | Cao, trên lưới nốt giá | Trầm và Trung đi vòng hợp âm | Chung hợp đồng. Ba pattern riêng (Phase 3 tách): `study` (Sor đều), `villa_pattern` (Villa cuộn), `preludio` (Barrios *La Catedral*, bass mỗi hai ô + chuông) |
| Thánh ca | Chương dưới 90 BPM; câu nghỉ sau hai câu tremolo; Sor khi `bpm <= 72`, `selloff`, `section.trio` ở thứ, hoặc `calm` (Phase 3); Villa khi `bpm <= 72`, band `p`, `calm`, hoặc `section.trio` (Phase 3) — trừ câu thân đầu ở `bpm >= 90` | Cao (hoặc Trầm ở `thumb_cantabile`) hát đường giá | Bè còn lại đỡ hợp âm, song thanh hoặc khung chấm dôi | Chung vai hát. Phase 1: `andante` (Barrios), `chord_melody` (Villa *Étude No. 11*), `elegiaque` (Sor hành khúc chấm dôi + lament). Phase 3 thêm: `cantabile` (Sor song thanh quãng 3/6) và `thumb_cantabile` (Villa/Barrios giai điệu ngón cái ở bè Trầm) |
| Tremolo | 90–140, rõ ở 100–120 | `a–m–i` lặp một nốt đen | Ngón cái mỗi trùm, gốc và quãng 5 | Một lưới (`tremolo`). Palette hiện chỉ Barrios có |
| Scale (lớp phủ) | Mọi tempo; giá trị nốt đổi theo tempo | Cao, một mình | Trầm của pattern chủ, hoặc nghỉ | Chung grammar cấp câu. Phủ lên đoạn đỉnh/kết của pattern chủ; đệm không dùng chung |
| Điệu | `bpm > 100`, meter 4/4 hoặc 6/8, câu chạy, khác `calm` | Cao vẫn là nốt giá | Dáng đi lệch phách ở Trầm và Trung | Không dùng chung: Phase 2 có `choro` (4/4) và `polca` / `hemiola` (6/8); Phase 3 thêm `vals` (*Valse Venezolano* đan 6/8–3/4 ở `section.trio` 6/8) của Barrios |

Arpeggio là phương án còn lại: tempo nào cũng đứng được. Tremolo không có bản thưa. 96 và 108 vẫn là lưới đầy. Dưới 90, họ này vắng mặt. 140 là trần cửa, không phải BPM của chương nào trên bản đồ.

Điệu nhanh của Barrios đứng từ `bpm > 100`, ở 4/4 hoặc 6/8, khi giai điệu đang chạy và character khác `calm`. 3/4 không có điệu đó. Hành khúc chấm dôi của Sor là pattern `elegiaque` thuộc họ Thánh ca (bật ở chương chậm `bpm <= 72` và ở `1D` 88 BPM khi `selloff` ngay từ câu thân đầu; ở `bpm >= 90` thì bật từ câu thân thứ hai khi `selloff` hay `section.trio` ở thứ), không dùng cửa của choro.

## 3. Bộ chọn

Mọi ô thuộc `_PEDAL` (`intro`, `outro`, `warmup`, `cooldown`) được tách riêng theo từng ô trước bộ chọn câu: bass gốc ngân cả ô, Trung nghỉ, Cao ngân theo dữ liệu, không tremolo, không thánh ca, không dance (ở Phase 3, riêng `intro` và `warmup` của Barrios được điểm thêm motif chuông Preludio trên bè Cao khi còn `bell_budget`).

Với các câu thân bài, bộ chọn khóa theo câu (`Phrase`). Band và `character` của câu đều đọc tại ô chứa nốt đỉnh (`phrase.apex`): lấy `band_at[apex_bar]`, và lấy `character_at[apex_bar]` nếu có (như `1W` đổi character mỗi phiên 32 ô), ngược lại lấy `character` của chương. Scale và nốt dẫn của điệu được chiếm một đoạn trong câu mà không đổi pattern của cả câu.

Một chương chỉ có một `Score.divisions`: bằng `4` khi chương có bất kỳ ô móc kép nào (Barrios ở `bpm >= 90`, hoặc chương có đoạn scale móc kép ở Phase 3), bằng `2` khi cả chương chỉ dùng lưới móc đơn. Trong chương `divisions = 4`, các ô pedal, arpeggio, thánh ca và đuôi kết câu vẫn phát `NoteEvent` trên cùng `Score` có `divisions = 4` (với `duration_beats` tính bằng phách đen: `0.5` cho móc đơn, `1.0` cho nốt đen), không đổi `divisions` giữa chương.

Lọc rồi mới xếp. Một pattern ngoài cửa tempo, ngoài meter, hoặc trái hình câu thì bị loại trước khi xét thứ tự.

1. Câu thân đầu chương khi `bpm >= 90` → pattern arpeggio khai của nhà đó (Phase 1–2 dùng arpeggio chung; Phase 3 tách thành `preludio` cho Barrios, `study` cho Sor, `villa_pattern` cho Villa). Bước này đứng trước bước 2–4, nên ở `bpm >= 90` câu thân đầu luôn là arpeggio kể cả khi câu giữ nốt, Sor `selloff`, hay Villa `calm` / band `p`. Chương dưới 90 BPM bỏ qua bước này để vào thẳng thánh ca ở bước 3 ngay từ câu thân đầu.
2. Câu có nốt giai điệu giữ từ hai phách đen (≥ 4 móc đơn liền cùng cao độ trên đường giai điệu đã nén), và palette có tremolo, và BPM nằm trong 90–140 → `tremolo`. Câu vừa có nốt chạy vừa có một nốt giữ từ hai phách đen vẫn là câu tremolo. Đã có hai câu tremolo liền trước thì câu này chuyển sang họ Thánh ca (`andante` ở Phase 1–2; ở Phase 3, nếu câu thuộc `section.trio` hoặc `section.bridge` thì là `thumb_cantabile`, ngược lại là `andante`).
3. Câu đang ở vai hát:
   - **Barrios**: khi BPM dưới 90 (`andante` ở Phase 1–2; ở Phase 3, câu thuộc `section.bridge` — tức đoạn giữa của chương chậm 3/4 — dùng `thumb_cantabile`, hai đoạn ngoài dùng `andante`), hoặc ở Phase 3 khi `bpm >= 90` mà câu chạy đang ở `calm` và thuộc `section.trio` (`thumb_cantabile`).
   - **Sor**: khi chương chậm (`bpm <= 72`), `selloff`, hoặc section mang `section.trio` ở mode thứ (`elegiaque`); ở Phase 3 thêm khi `calm` tại `bpm > 72` (`cantabile` song thanh quãng 3/6 — từ câu thân đầu ở 88 BPM, hoặc từ câu thân thứ hai khi `bpm >= 90`).
   - **Villa**: ở Phase 1–2 khi chương chậm (`bpm <= 72`), band `p`, hoặc `calm` (`chord_melody`); ở Phase 3, câu thuộc `section.trio` (ở 108/120 BPM) hoặc thuộc `section.bridge` (đoạn giữa chương chậm `bpm <= 72`) dùng `thumb_cantabile`, các câu còn lại thỏa `bpm <= 72`, band `p`, hoặc `calm` dùng `chord_melody`.
   `section.trio` và `section.bridge` là hai cờ có sẵn trên `FormSection` trong `span.py`, chỉ gắn cho đoạn giữa của chương scherzo/tháng khép 6/8 (`trio=True`) và đoạn giữa của chương chậm 3/4 (`bridge=True`); không đọc `regime_slot == 1` trực tiếp cho `thumb_cantabile` (để không bật nhầm ở câu giữa của `1D`, phiên thứ hai của `1W`, hay các chương 4/4), và không dùng `trio_bars` của `form.py` (vốn chỉ lấy nửa đầu câu). Vì chương thứ là `selloff` hoặc `volatile` đóng cửa xuống mà `selloff` đã bật `elegiaque` ở mọi câu sau câu mở, cửa `section.trio` của Sor thực chất bắt thêm đoạn giữa của chương `volatile` đóng cửa xuống.
4. Câu đang chạy (mọi nốt trong câu đều ngắn hơn hai phách đen), character khác `calm`, `bpm > 100`, meter 4/4 hoặc 6/8, và palette có điệu của meter đó → `dance` (`choro` ở 4/4; ở 6/8 là `polca` / `hemiola` từ Phase 2, riêng câu chạy thuộc `section.trio` của 6/8 ở Phase 3 là `vals`). Phase 1 chưa có nhánh này: câu chạy rơi xuống bước 5.
5. Còn lại → arpeggio của nhà đó (`study`, `villa_pattern`, hoặc `preludio` rút gọn không chuông ở Barrios).

Scale và Grand Solo không phải bước thứ 6 trong bộ chọn: ở Phase 3, Scale phủ một đoạn ở đỉnh hoặc ở hai phách cuối câu đóng trên pattern đã chọn khi còn ngân sách; Grand Solo nâng bậc figuration và điểm khối đầu section / caesura trên các câu của Sor đã chọn `study` ở bước 5 khi `bpm >= 90`, từ câu thân thứ hai trở đi, và character là `rally` hoặc `volatile` (`1D` ở 88 BPM giữ `study` thường, trừ khi `selloff` đã vào `elegiaque` hoặc `calm` vào `cantabile`).

Hệ quả trên bản đồ đang chạy:

| Chỗ | BPM, meter | Barrios | Sor | Villa |
|---|---|---|---|---|
| `1D` | 120 / 100 / 88, 4/4 | Câu thân đầu: arpeggio (Phase 3: `preludio`). Từ câu 2 — ngân: `tremolo` (câu thứ 3 liên tiếp: `andante`); chạy (Phase 2, khác `calm`): `choro`; chạy `calm`: arpeggio. (`1D` không có `trio`/`bridge` nên không có `thumb_cantabile`) | 88 < 90 nên không qua bước 1 và không bật Grand Solo: `selloff` là `elegiaque` cả bài; `calm` (Phase 3) là `cantabile` cả bài; còn lại `study` thường | Câu thân đầu: arpeggio. Từ câu 2: `calm` hoặc band `p` là `chord_melody`; còn lại arpeggio (100 không vượt `bpm > 100`, không có `trio`/`bridge`) |
| `1W` | 90, 4/4 | Câu thân đầu: arpeggio. Từ câu 2: `tremolo` ở sàn cửa nếu câu ngân (câu thứ 3 liên tiếp: `andante`); chạy: arpeggio (`1W` không có `trio`/`bridge` nên không có `thumb_cantabile`) | Câu thân đầu: arpeggio. Từ câu 2: `selloff` là `elegiaque`; `calm` (Phase 3) là `cantabile`; `rally`/`volatile` là `study` (Phase 3 phủ Grand Solo) theo `character_at` | Câu thân đầu: arpeggio. Từ câu 2: `calm` hoặc band `p` là `chord_melody`; còn lại arpeggio theo `character_at` / band của câu |
| Chương 96 hoặc 100 BPM, 4/4 | 96, 100 | Câu thân đầu: arpeggio. Từ câu 2: `tremolo` nếu câu ngân (câu thứ 3 liên tiếp: `andante`); chạy: arpeggio (điệu đòi `bpm > 100`, không có `trio`/`bridge`) | Câu thân đầu: arpeggio. Từ câu 2: `selloff` là `elegiaque`; `calm` (Phase 3) là `cantabile`; `rally`/`volatile` là `study` (Phase 3 phủ Grand Solo) | Câu thân đầu: arpeggio. Từ câu 2: `calm` hoặc band `p` là `chord_melody`; còn lại arpeggio |
| Chương chậm `1M` II, `3M` II, tháng giữa `1Y` | 72, 60, 66, đều 3/4 | Phase 1–2: `andante` cả thân chương (kể cả câu đầu). Phase 3: đoạn giữa (`section.bridge`) là `thumb_cantabile`, hai đoạn ngoài là `andante`. Không tremolo, không choro | `elegiaque` cả thân chương (kể cả câu thân đầu, kể cả khi `calm`) | Phase 1–2: `chord_melody` cả thân chương (kể cả câu đầu). Phase 3: đoạn giữa (`section.bridge`) là `thumb_cantabile`, hai đoạn ngoài là `chord_melody` |
| Scherzo `1M`, tháng khép `1Y` | 120 và 108, 6/8 | Câu thân đầu: arpeggio. Từ câu 2 — ngân: `tremolo` đầy, ba trùm nốt đen (câu nghỉ thứ 3: `thumb_cantabile` nếu ở `section.trio`, ngược lại `andante`); chạy khác `calm`: Phase 2 là `polca` (band `f`: `hemiola`), Phase 3 ở `section.trio` là `vals`; chạy `calm`: ở `section.trio` (Phase 3) là `thumb_cantabile`, ngoài `trio` (hoặc Phase 1–2) là arpeggio | Câu thân đầu: arpeggio. Từ câu 2: `elegiaque` khi `selloff` hoặc `section.trio` ở thứ; `calm` (Phase 3, ngoài trio thứ) là `cantabile`; còn lại `study` (Phase 3 phủ Grand Solo) | Câu thân đầu: arpeggio. Từ câu 2: ở Phase 3, câu thuộc `section.trio` là `thumb_cantabile`; ngoài `trio` (hoặc ở Phase 1–2), `calm` hoặc band `p` là `chord_melody`, còn lại arpeggio |
| Chương III `3M` | 108, 4/4 | Như `1D` của Barrios (không có `trio`/`bridge`, nên câu nghỉ thứ 3 là `andante`, câu chạy khác `calm` là `choro`, câu chạy `calm` là arpeggio) | Như chương 96/100 BPM của Sor | Như chương 96/100 BPM của Villa |

`1M` I và IV, tháng 12 của `1Y`, và `3M` I là các chương 96 BPM; tháng mở của `1Y` là 100 BPM.

### 3.1. Diễn biến thị trường điều khiển bộ chọn như thế nào

Ngoài tốc độ (`bpm`), nhịp (`meter`) và mode Trưởng/Thứ của chương, bộ chọn đọc bốn tín hiệu thị trường ngay trên từng `Phrase` (sau khi bước 1 đã giữ câu thân đầu của chương `bpm >= 90` làm arpeggio mở bài):

- **Thị trường đi ngang (`calm`) hoặc thanh khoản cạn (`band == "p"` tại `phrase.apex`)** → **Lắng xuống, hát nội tâm**:
  - **Sor**: khi `character == "calm"` và `bpm > 72`, chuyển sang hát hai bè song thanh quãng 3/6 (`cantabile`, Phase 3; ở chương chậm `bpm <= 72` thì vẫn là `elegiaque`). Nếu chỉ có `band == "p"` mà character không phải `calm` hay `selloff`, Sor vẫn ở `study` nhưng rút thưa còn 1 nốt bass + 1 nốt Trung.
  - **Villa**: khi `character == "calm"` hoặc `band == "p"` (hoặc `bpm <= 72`), gảy hợp âm khối ngân chậm (`chord_melody`, trừ các câu giữa `section.trio` / `section.bridge` ở Phase 3 dùng `thumb_cantabile`).
  - **Barrios**: khi `calm`, câu có nốt giữ $\ge 2$ phách đen ở `bpm >= 90` vẫn ngân `tremolo` (câu thứ ba liên tiếp nghỉ sang `thumb_cantabile` nếu ở `section.trio`, ngược lại sang `andante`); câu chạy không bật điệu nhảy (vì bước 4 chặn `calm`) mà về `thumb_cantabile` nếu ở `section.trio` (Phase 3) hoặc về arpeggio.
- **Thị trường bán tháo (`selloff`) hoặc đoạn giữa `section.trio` ở chương Thứ** → **Trầm hùng, bi tráng**:
  - **Sor**: vào hành khúc tang chấm dôi kèm bass lament đi xuống từng bậc (`elegiaque` — ngay từ câu thân đầu nếu `bpm < 90`, và từ câu thân thứ hai nếu `bpm >= 90`).
  - **Villa**: ở chương chậm (`bpm <= 72`) chơi `chord_melody` (hoặc `thumb_cantabile` ở `section.bridge` Phase 3) trên hợp âm thứ/treo; ở `bpm >= 90` (từ câu thân thứ hai), câu `selloff` thuộc `section.trio` (Phase 3) chơi `thumb_cantabile`, câu có `band == "p"` chơi `chord_melody`, còn câu `mp–f` ngoài `trio` cuộn `villa_pattern` trên hòa âm thứ và hợp âm treo của dialect Villa.
  - **Barrios**: đi vòng hòa âm quãng 5 thứ (`Fm → Bb → Eb → Ab → D7 → G7`) và hợp âm sext tăng `Ab+6` của `BarriosDialect` (Phase 2); tay phải vẫn theo đúng cửa tempo và hình câu (`andante` / `thumb_cantabile` khi `bpm < 90`; `tremolo` khi câu ngân ở `bpm >= 90`; `choro`, `polca`/`hemiola` hoặc `vals` khi câu chạy ở `bpm > 100`; arpeggio khi câu chạy ở `90–100 BPM`).
- **Thị trường tăng mạnh hoặc giằng co thanh khoản lớn (`rally` / `volatile`, band `mf–f`)** → **Động năng cao, đẩy tiết tấu tới trước**:
  - Khi **giá giữ nhịp / tích lũy trên đường đi** (trong câu có nốt giữ $\ge 2$ phách đen): Barrios ở `bpm >= 90` bật `tremolo` căng đầy; Sor và Villa cuộn arpeggio dày (`study` có phủ `Grand Solo` khi `bpm >= 90`, và `villa_pattern`).
  - Khi **giá nhảy liên tục từng mốc** (mọi nốt trong câu $< 2$ phách đen): Barrios ở `bpm > 100` bật điệu nhảy lệch phách (`choro` ở 4/4, `polca`/`hemiola` hoặc `vals` ở 6/8); Sor ở `bpm >= 90` bật biến tấu `Grand Solo` dày dần theo họ câu; Villa nhấn lệch nhịp `3+3+2` (tresillo) ở `volatile` 4/4.
  - Khi câu **leo dốc mạnh (`phrase.rise >= MIN_RISE`) hoặc phá đỉnh (`breakout`)**: ở Phase 3, cả ba nhà được phủ thêm đoạn chạy `Scale` lao thẳng vào nốt đỉnh ở phách mạnh. Riêng các câu đã được chọn làm `chord_melody` ở bước 3 (chương chậm `bpm <= 72`, hoặc `calm`, hoặc `band == "p"`), khi có `phrase.rise >= MIN_RISE` thì dồn dày cú hợp âm khối về phía đỉnh câu theo mục 6.2.

### 3.2. Khớp nối khi đổi pattern (Transition, Giảm tốc kết cấu & Điểm thở)

Giá chạy liên tục từng móc đơn, nhưng trên đàn guitar thật không thể cắt dán đột ngột từ một câu 16 móc kép (`tremolo`, `choro`, `polca`) sang một câu hợp âm tĩnh (`andante`, `chord_melody`, `elegiaque`) mà không có điểm thở. Để chuyển pattern mượt mà mà **không làm lệch tổng số móc đơn hay con trỏ playhead**, biên giữa câu `phrase_i` và câu kế tiếp `phrase_{i+1}` (khi cả hai đều nằm trong thân bài, không phải ô `_PEDAL`) tuân theo ba quy luật khớp nối sau:

1. **Giảm tốc kết cấu ở cuối câu mật độ cao (Textural Tapering — từ Phase 1 cho `tremolo`, Phase 2 cho `dance`)**:
   - **Với `tremolo`**: tắt lặp `a–m–i` ở **hai phách đen cuối** (`4 móc đơn = 8 móc kép`) không chỉ khi câu đóng (`phrase.closes == True`), mà cả khi câu kế tiếp **đổi sang một pattern khác `tremolo`** (ví dụ sang `andante`, `choro`, `polca`, hoặc `arpeggio`), miễn là câu `tremolo` đó dài từ **bốn phách đen trở lên** (để phần trước vẫn còn ít nhất hai phách tremolo). Trong hai phách đen cuối đó, bè Cao giữ ngân nốt dữ liệu và bè dưới trả về arpeggio kết câu nhẹ (hoặc đoạn scale đi xuống ở Phase 3).
   - **Với `dance` (`choro`, `polca`, `hemiola`, `vals` — Phase 2–3)**: nếu câu kế tiếp **không còn là `dance`**, thì ở phách đen cuối cùng của câu `dance`, bè Trung bỏ các móc kép lẻ và bè Trầm **tắt nốt dẫn bán cung ở móc kép cuối ô** (móc kép 15 của 4/4 hoặc móc kép 11 của 6/8 nghỉ thay vì trượt bán cung, tránh đẩy đà giả vào một câu tĩnh).
2. **Khe thở một móc đơn tại biên đổi pattern (Pattern-Change Breath — từ Phase 1)**:
   - Khi `pattern(phrase_i) != pattern(phrase_{i+1})`, móc đơn cuối cùng của câu trước (`eighth = phrase_i.end - 1`, ngay trước khi câu mới mở ra) được dùng làm **điểm nhấc tay lấy hơi**:
     - Nếu `phrase_i` kết thúc bằng một nốt giữ dài $\ge 2$ móc đơn: rút ngắn nốt cuối của bè Cao và bè Trung đi **1 móc đơn**, biến móc đơn `phrase_i.end - 1` thành dấu lặng (`midi=None`) ở cả bè Cao và bè Trung.
     - Nếu `phrase_i` kết thúc bằng các nốt móc đơn rời liên tiếp (câu chạy mở) và câu kế tiếp đổi sang một **họ pattern khác** (ví dụ từ `dance` hoặc `arpeggio` sang họ Thánh ca hoặc `tremolo`) với câu `phrase_i` dài từ 4 móc đơn trở lên: nhường nốt ở móc đơn cuối `phrase_i.end - 1` của bè Cao và bè Trung thành **1 móc đơn lặng** (`midi=None`). Bỏ một móc đơn cuối câu chạy này trên lưới có sẵn giúp hai câu tách bạch tự nhiên như người chơi thật lấy hơi mà đồng hồ chương không lệch một giây nào.
3. **Nốt bass bắc cầu khi đi từ Thưa sang Dày (Anacrusis / Pickup Bass — Phase 2–3)**:
   - Khi chuyển từ một câu họ Thánh ca (`andante`, `chord_melody`, `elegiaque`, `cantabile`) sang một câu động năng cao (`tremolo`, `dance`, hoặc `study` có phủ `Grand Solo`), tại đúng móc đơn lấy hơi `phrase_i.end - 1` (khi bè Cao và bè Trung đang nghỉ), **bè Trầm (voice 3, ngón cái `p`)** được gảy nhẹ một nốt dẫn móc đơn (quãng 5 hoặc bậc thang liền kề dẫn vào gốc hợp âm đầu câu `phrase_{i+1}`, velocity `_INNER`) để tạo đà bước qua vạch câu — **trừ khi** biên đó đang là **caesura của Grand Solo** (mục 8: trước câu chứa đỉnh cao nhất của section mà câu trước đóng), khi đó caesura thắng và cả ba bè (kể cả bè Trầm) cùng lặng hoàn toàn ở `phrase_i.end - 1`.

## 4. Bản đồ nhịp

Đã code trong `span.py`. Guitar hoán meter cùng số móc đơn mỗi ô, giữ số ô và BPM.

| Khung | Chương | Meter guitar | BPM |
|---|---|---|---|
| `1D` | Bản ngày (34 ô) | 4/4 | Sor 88, Villa 100, Barrios 120 |
| `1W` | Bản tuần (32 ô/phiên) | 4/4 | 90 |
| `1M` | I, IV | 4/4 | 96 |
| `1M` | II (`section.bridge` ở đoạn giữa) | 3/4 | 72 |
| `1M` | III (`section.trio` ở đoạn giữa) | 6/8 | 120 |
| `3M` | I, III | 4/4 | 96 và 108 |
| `3M` | II (`section.bridge` ở đoạn giữa) | 3/4 | 60 |
| `1Y` | Tháng mở, tháng 12 | 4/4 | 100 và 96 |
| `1Y` | Tháng giữa (`section.bridge` ở đoạn giữa) | 3/4 | 66 |
| `1Y` | Tháng khép (`section.trio` ở đoạn giữa) | 6/8 | 108 |

`1D` giữ 4/4, 34 ô (không có `bridge` hay `trio`). `1W` giữ 4/4, 90 BPM (`regime_slot` là chỉ số phiên 0..4, không có `bridge` hay `trio`). Cờ `trio` trên scherzo `1M` III và tháng khép `1Y` cùng cờ `bridge` trên chương chậm 3/4 (`1M` II, `3M` II, tháng giữa `1Y`) giữ nguyên từ nhánh giao hưởng. Đồng hồ guitar trùng giao hưởng: `(970.0, 1530.0, 2840.1)`, trần `1Y` là `47:21`.

Trong chương, 4/4 có thể nhấn 3+3+2. Luật này đã có cho Villa: ô `mf`/`f`, character `volatile`, tối đa hai ô liền, chỉ 4/4. Các nhà khác chưa dùng. Hemiola 6/8 (nhấn móc đơn 0, 2, 4) là bản band `f` của polca, Phase 2, không phải một lớp accent chung.

## 5. Họ Arpeggio — ba pattern (`study`, `villa_pattern`, `preludio`)

Hợp đồng chung: bè Cao là đường giá đã nén, trên lưới móc đơn. Vòng chỉ gồm Trầm và Trung, nằm dưới giai điệu đang vang. Không nốt Trung nào trùng hoặc cao hơn Cao. Band làm vòng thưa hoặc dày, không đổi họ.

**Đang chạy.** Một vòng dùng chung. Bass gốc ở các phách mạnh của meter, gập vào dải Trầm. Trung lấy âm hợp âm, số nốt theo band; ô `p` một nốt. Villa (`rolling`) dày hơn và có tresillo như mục 4. Ô pedal chỉ bass gốc.

**Phase 1** vẫn gọi hàm này cho câu mở (ở `bpm >= 90`) và câu không rơi vào tremolo hay thánh ca. Chưa tách ba pattern.

**Phase 3** tách thành ba pattern độc lập trong họ Arpeggio:

- **`study` (Sor)**: 4/4 như bảng band hiện có (gốc móc 0, quãng 5 móc 4, arpeggio các móc yếu khi `mf`/`f`). 6/8 nhóm ở móc 0 và 3. 3/4 phách mạnh móc 0, trọng phụ móc 4. Khi câu thuộc diện **Grand Solo** (`bpm >= 90`, `rally` hoặc `volatile`, từ câu thân thứ hai trở đi), pattern nền vẫn là `study` nhưng được bộ biến tấu cấp câu ở mục 8 nâng mật độ theo họ câu (`level 0 → 1 → 2`).
- **`villa_pattern` (Villa — *Étude No. 1*)**: vòng cố định dưới giai điệu. 4/4 đủ tám móc khi `mf`/`f`. 6/8 một vòng, nhấn móc 0 và 3. 3/4 band `f` nhấn móc 0 và 3, đó là hemiola của vòng này, không phải điệu Barrios. Nốt bass cuối ô ở band `f` được là dẫn bán cung về gốc ô sau. Bè Trung lấy âm màu khi hợp âm là sus hoặc add9. Không gọi `jazz_chord`. Hiệu ứng **campanella** là quy tắc ngân trong pattern này: khi nốt bè Trung vừa gảy và nốt bè Cao kế tiếp gán được trên hai dây khác nhau theo mô hình dây (mục 11), nốt Trung được kéo dài thêm 1 móc đơn để ngân chồng qua nốt Cao.
- **`preludio` (Barrios — *La Catedral* Preludio Saudade)**: một pattern arpeggio đặc trưng riêng, bật ở câu thân đầu của mỗi chương Barrios `bpm >= 90` (cùng các câu thân bài ở bước 5 dưới dạng rút gọn không chuông; các ô `_PEDAL` `intro`/`warmup` vẫn giữ kết cấu pedal với bass ngân cả ô và Trung nghỉ, chỉ nhận motif chuông). Trong câu `preludio`, đệm chảy đều móc đơn theo vòng âm hợp âm dưới giai điệu nhưng chậm và trầm mặc hơn `villa_pattern`: bass gốc chỉ đánh ở đầu mỗi **hai ô** (ngân qua hai ô), velocity vòng Trung thấp hơn giai điệu khoảng 8 đơn vị. Ở các ô mở (`intro`, `warmup`) và câu thân đầu chương, Barrios mang thêm **motif chuông** trên bè Cao (thay vào móc đơn yếu hoặc đuôi nốt giữ ≥ 2 móc đơn, giữ bè Cao đơn âm và không đè lên nốt giá ở phách mạnh): tối đa một nốt mỗi hai ô, cao độ lấy pitch-class của đỉnh câu đặt ở quãng tám cao nhất có vang ≤ 83 (`guitar_ceiling`), chỉ khi `bell_budget` còn. Phiên phẳng (biên độ ≤ 0.5%) không có chuông. Harmonics thật chỉ xuất nếu sample trả lời; mặc định là nốt cao ngân.

## 6. Họ Thánh ca — năm pattern (`andante`, `chord_melody`, `elegiaque` ở Phase 1; `cantabile`, `thumb_cantabile` ở Phase 3)

Năm pattern độc lập cùng đóng vai hát. Ở ba pattern Phase 1 (`andante`, `chord_melody`, `elegiaque`), giai điệu là nốt trên, hợp âm hoặc khung chấm dôi đỡ cùng nó ở các mốc phách của meter, bè Trung thưa và được ngân, bass thuộc hợp âm; khối đúng ba nốt, Trung dưới Cao; ở 3/4, cú khối chuẩn chỉ móc 0, móc 4 chỉ thêm ở ô đỉnh câu hoặc ô kết câu. Sang Phase 3, họ này mở thêm hai cách hát kinh điển của guitar cổ điển: hát hai bè song thanh quãng 3/6 (`cantabile` của Sor) và đảo giai điệu xuống bè Trầm cho ngón cái hát như tiếng Cello (`thumb_cantabile` của Villa-Lobos và Barrios).

### 6.1. Pattern `andante` (Barrios — *Andante Religioso*)

Nhà của mọi chương Barrios dưới 90, và của câu nghỉ sau hai câu tremolo (kể cả ở 4/4 hoặc 6/8, 90–120 BPM). Lưới cú khối ba nốt (Trầm gốc + Trung âm hợp âm dưới Cao + Cao giai điệu) khóa theo meter:

- 4/4: móc đơn 0 và 4, mỗi cú Trầm và Trung ngân 4 móc đơn.
- 6/8: móc đơn 0 và 3 (đầu mỗi nhóm chấm dôi), mỗi cú Trầm và Trung ngân 3 móc đơn.
- 3/4: móc đơn 0 (Trầm và Trung ngân cả ô 6 móc đơn); riêng ô chứa đỉnh câu (`phrase.apex`) hoặc ô kết câu đóng thì thêm một cú khối ở móc đơn 4 (khi đó cú móc 0 ngân 4 móc, cú móc 4 ngân 2 móc).

Giữa các móc khối trên, Trầm và Trung giữ ngân, không gảy nốt mới; nếu đường giai điệu có nốt dữ liệu mới ở các móc đơn khác thì chỉ bè Cao đánh nốt đó. Chưa viết luật đảo 6/3: tổng phổ Andante có planing, tài liệu này không lấy đó làm hợp âm mới và cũng chưa khóa thành luật bè.

### 6.2. Pattern `chord_melody` (Villa — *Étude No. 11*)

Chương chậm (`bpm <= 72`, cả thân chương), và chương từ 90 BPM trở lên (từ câu thân thứ hai) khi band câu là `p` hoặc character là `calm` (với Villa, mọi chương không chậm đều có `bpm >= 90`). Nốt Trung là âm 3 hoặc âm 7; với `suspended` thì là quãng 2, quãng 4 hoặc b7. Lưới cú khối ba nốt (Trầm + Trung + Cao) và cách dồn khi câu đang lên (`phrase.rise >= MIN_RISE`, với `MIN_RISE = 3` nửa cung) khóa theo từng meter, không chèn khối vào móc yếu của 6/8 hay móc 2 của 3/4:

- **4/4**: chuẩn ở móc đơn `0` và `4` (cách 4 móc). Khi câu có `phrase.rise >= MIN_RISE`, các ô từ đầu câu tới ô chứa `phrase.apex` dồn thành mỗi phách đen một khối ở móc đơn `0, 2, 4, 6` (cách 2 móc); các ô sau đỉnh hoặc câu không đủ `MIN_RISE` giữ `0, 4` và cú cuối ngân hết ô.
- **6/8**: chuẩn ở móc đơn `0` (đầu ô, ngân cả ô 6 móc đơn); khi câu có `phrase.rise >= MIN_RISE`, đúng hai ô — **ô chứa `phrase.apex` và ô ngay trước nó** (nếu thuộc cùng câu) — dồn thành cả hai đầu nhóm chấm dôi ở móc đơn `0` và `3` (mỗi cú ngân 3 móc đơn). Các ô khác trong câu chỉ đánh khối ở móc `0`. Không bao giờ đánh khối ở móc đơn `1, 2, 4, 5`.
- **3/4**: chuẩn ở móc đơn `0` (ngân cả ô 6 móc đơn); thêm cú khối thứ hai ở móc đơn `4` (cú móc 0 ngân 4 móc, cú móc 4 ngân 2 móc) tại các ô từ đầu câu tới ô chứa `phrase.apex` khi `phrase.rise >= MIN_RISE`, hoặc tại ô chứa `phrase.apex` của mọi câu, hoặc tại ô kết của câu đóng (`phrase.closes`). Không bao giờ đánh khối ở móc đơn `2`.

Một hairpin theo cả câu. Riêng câu chương chậm, band `f`, `volatile`, có breakout: Phase 3 mới phủ đoạn scale lên đỉnh câu; Phase 1 câu đó vẫn là `chord_melody`.

### 6.3. Pattern `elegiaque` (Sor — *Fantaisie élégiaque*)

Bật ở chương chậm (`bpm <= 72`, cả thân chương), ở `1D` (`88 BPM < 90`, cả thân chương từ câu đầu) khi `selloff`, hoặc ở chương `bpm >= 90` (từ câu thân thứ hai, vì bước 1 giữ câu thân đầu là arpeggio) khi `selloff` hay khi section mang `section.trio` ở mode thứ. Scherzo 120 và tháng khép 108 đều đi cửa `section.trio` này. `3M` không có trio.

Pattern khung là bass hành khúc chấm dôi theo meter, kết hợp hai thủ pháp cấp câu (bass lament đi xuống ở kết câu và appoggiatura):

- 4/4: mỗi nửa ô, móc 0 dài 3, móc 3 ngắn 1 đi xuống liền bậc.
- 3/4: móc 0 dài 3, móc 3 ngắn 1 đi xuống, móc 4 dài 2. Ô kết câu, bass ngân từ móc 0.
- 6/8: móc 0 dài 2, móc 2 ngắn 1, móc 3 dài 2, móc 5 ngắn 1.

Hai ô cuối câu đóng ở thứ: bass ưu tiên đi xuống liền bậc theo thang, khi hợp âm chứa những bậc đó. Trung thưa hơn study một bậc. Appoggiatura: tối đa một mỗi câu, khi nốt dữ liệu ở phách mạnh được giữ từ hai móc đơn và nốt dữ liệu kế tiếp (sau nốt phách mạnh đó) lệch đúng một bậc thang. Móc đơn đầu của nốt phách mạnh được thay bằng nốt thang ngoài hợp âm tạo thành bước đi liền bậc cùng chiều với bước sang nốt dữ liệu kế tiếp (nếu nốt dữ liệu kế tiếp thấp hơn nốt phách mạnh một bậc thang thì nốt tựa nằm cao hơn nốt phách mạnh một bậc thang, tạo ba bậc đi xuống liên tiếp; nếu nốt kế tiếp cao hơn một bậc thì nốt tựa nằm thấp hơn một bậc), rồi móc đơn thứ hai trả về đúng nốt dữ liệu của phách mạnh. Không có fill kết câu.

### 6.4. Pattern `cantabile` — Song thanh quãng 3 / quãng 6 (Sor — *Op. 6 No. 10*, *Op. 31 No. 21*) — Phase 3

Bật cho Sor ở `bpm > 72` khi character của câu là `calm` (ở `1D` `88 BPM < 90` thì từ câu thân đầu; ở chương `bpm >= 90` thì từ câu thân thứ hai trở đi vì bước 1 giữ câu thân đầu là arpeggio). Thay vì rải arpeggio `study`, bè Cao (voice 1) và bè Trung (voice 2) đi **song song cùng tiết tấu** với đường giai điệu đã nén: tại mỗi nốt giai điệu của bè Cao, bè Trung đánh đồng thời một nốt thuộc thang của mode nằm thấp hơn bè Cao một **quãng 3** (ưu tiên 2 bậc thang dưới Cao) hoặc một **quãng 6** (5 bậc thang dưới Cao khi quãng 3 rơi dưới `guitar_mid_low` hoặc trùng bass), giữ trong [`guitar_mid_low`, `guitar_mid_high`] và nghiêm ngặt `Trầm < Trung < Cao`. Bè Trầm (voice 3) chỉ đánh gốc hợp âm thưa ở phách mạnh đầu ô (cộng móc 4 ở 4/4 khi band `mf`/`f`), tạo kết cấu song ca cổ điển (*cantabile a due voci*) trong sáng, tách hẳn màu tang của `elegiaque`.

### 6.5. Pattern `thumb_cantabile` — Giai điệu ngón cái ở bè Trầm (Villa *Prélude No. 1* / Barrios *Julia Florida*) — Phase 3

Bật ở Phase 3 theo đúng thứ tự bước 2–3 của bộ chọn mục 3, chỉ dựa trên hai cờ `section.trio` và `section.bridge` (không đọc `regime_slot == 1` trần, nên `1D`, `1W`, và các chương 4/4 không bao giờ vào `thumb_cantabile`):
- **Với Villa**: tại mọi câu thuộc `section.trio` (scherzo `1M` 120 BPM, tháng khép `1Y` 108 BPM) hoặc thuộc `section.bridge` (đoạn giữa chương chậm 3/4 ở `72, 60, 66 BPM`).
- **Với Barrios**: (a) ở chương dưới 90 BPM, tại các câu thuộc `section.bridge` (đoạn giữa chương chậm 3/4); (b) ở chương từ 90 BPM trở lên, chỉ tại câu nghỉ sau hai câu `tremolo` liên tiếp (bước 2) khi câu đó nằm trong `section.trio`, hoặc tại câu chạy đang ở `calm` (bước 3) thuộc `section.trio` (vì câu ngân ở `trio` 108–120 BPM vẫn ưu tiên `tremolo` ở bước 2, và câu chạy khác `calm` ở `trio` 6/8 đi vào `vals` ở bước 4).

Đây là pattern duy nhất **đảo vai bè**:

- **Bè Trầm (voice 3 — ngón cái `p` hát giai điệu)**: đường giai điệu của câu được đặt vào cửa sổ Cello `48–64` vang (tức [`48 − semitones`, `64 − semitones`] viết, rộng 16 nửa cung) bằng cùng quy trình dịch + nén đơn điệu của `_place_melody`: thử dịch câu đi `{−12, −24}` nửa cung; nếu sau mức dịch đỡ lệch nhất vẫn còn nốt nằm ngoài cửa sổ [`48 − semitones`, `64 − semitones`] (ví dụ câu trải rộng hơn 16 nửa cung), nén đơn điệu theo bậc thang (`_compress_monotone`) vào trọn trong cửa sổ rồi `quantize_strong_beats` lại trên thang ở vùng đó. Ngón cái `p` hát nguyên vẹn tiết tấu đường giá với velocity nổi nhất (`_MELODY` / `_MELODY_APEX`, hơn bè đệm 8–10 đơn vị).
- **Bè Trung và Cao (voice 2 và voice 1 — hợp âm đệm phách yếu)**: nghỉ ở phách đầu ô (móc đơn `0`) để nhường chỗ cho nốt ngón cái mở phách, rồi chập nhẹ hai âm hợp âm (nằm cao hơn nốt giai điệu Trầm đang vang, velocity `_INNER`) ở các mốc phách yếu của meter:
  - `3/4`: chập ở móc đơn `2` và `4` (phách 2 và phách 3: *Trầm hát — chập — chập*, đúng mẫu *Prélude No. 1*).
  - `6/8`: chập ở móc đơn `2` và `5` (cuối mỗi nhóm chấm dôi, hoặc móc `1, 2` và `4, 5` khi band `mf`/`f`).
  - `4/4`: chập ở móc đơn `2` và `6` (phách 2 và phách 4, kiểu barcarola *Julia Florida*).

## 7. Tremolo — lưới đã chạy, cửa là Phase 1

Palette chỉ có Barrios. Cửa 90–140. Lưới dưới đây đã khóa trong `test_sonify_guitar.py`. Phase 1 đổi lúc nào gọi nó, không đổi trùm.

Một trùm là một nốt đen: bốn móc kép cùng một cao độ giai điệu. Cao độ chỉ đổi theo lưới móc đơn của dữ liệu, tức ở biên trùm. 4/4 có bốn trùm. 3/4 có ba. 6/8 cũng có ba, vì ô dài ba nốt đen; test scherzo 120 đòi mọi móc kép đều hát và ngón cái mở trùm ở beat 0, 1 và 2. Không gom 6/8 thành hai phách chấm với một ngón cái và năm lần lặp.

Ngón cái, velocity 58, đánh gốc và quãng 5 cùng lúc, ngân hết nốt đen. Hai nốt đó cùng voice Trầm. Bè lặp 52, 55, 54, 52. Ô đổi hợp âm: Trung đánh một nốt màu dưới giai điệu ở đầu ô, cùng lúc với ngón cái. Phách đó có bốn cao độ. Đó là ngoại lệ đã nghe, không siết về ba cao độ trong Phase 1 hay Phase 3.

Ô pedal không tremolo: giai điệu ngân theo câu, bass gốc. Tắt tremolo ở hai phách đen cuối (4 móc đơn = 8 móc kép) của câu đóng (`phrase.closes`) hoặc của câu tremolo mà câu kế tiếp đổi sang pattern khác (mục 3.2) là việc của Phase 1 (hiện chưa có trong `_tremolo`): trả hai phách cuối đó về arpeggio kết, hoặc về đoạn scale khi Phase 3 đã có, kèm khe thở 1 móc đơn ở `phrase.end - 1` khi đổi pattern. Luật cắt đuôi này chỉ cắt khi phần câu trước hai phách cuối vẫn còn ít nhất hai phách đen tremolo (tức câu dài từ bốn phách đen trở lên); nếu câu ngắn hơn bốn phách đen, không cắt mất đoạn tremolo duy nhất của câu.

Ép ngón giữ luật đang chạy: dưới 4%, không ở câu đầu, không trên móc kép tremolo.

## 8. Lớp phủ cấp câu: Scale và biến tấu Grand Solo — Phase 3

Không tạo họ pattern tay phải mới: đây là các thủ pháp cấp câu phủ lên pattern chủ đã được bộ chọn ở mục 3 ấn định.

**Scale (chạy dây)** dùng một grammar cho cả ba nhà. Bè Cao chạy liền bậc giữa hai mốc dữ liệu. Nốt đích trùng nốt giá hoặc nốt đỉnh. Nốt đầu được lệch 3–5 bậc thang để lấy đà, và phải thuộc thang. Nốt ở phách mạnh trong đoạn giữ nguyên cao độ so với bản không chạy. Hướng chạy cùng hướng câu, trừ đoạn đi xuống ở hai phách cuối câu đóng.

Giá trị nốt theo tempo của chương. Dưới 90, chạy bằng móc đơn (2–4 móc đơn mỗi đoạn). Từ 90, được dùng móc kép (4–8 móc kép mỗi đoạn; riêng perpetual tới 16 móc kép một ô). Cùng một luật «liền bậc, rơi đúng mốc».

Ngân sách: tối đa một đoạn mỗi câu, số ô có chạy không quá khoảng 15% ô của section, mỗi section còn ít nhất một câu không chạy. Âm lấy từ thang của mode. Barrios được một nốt dẫn bán cung ở móc kép ngay trước đích, tối đa một mỗi đoạn. Sor và Villa không lấy nốt đó trong đoạn scale.

Đệm không dùng chung. Sor và Villa giữ bass của pattern chủ, Trung nghỉ trong lúc chạy. Barrios: Trung nghỉ, bass gốc ở phách 1 và 3 (ở 6/8 là đầu hai nhóm chấm dôi, móc đơn 0 và 3). Dạng chạy cả ô (perpetual) chỉ Barrios, chỉ khi giá đứng yên từ một ô, band `f`, `volatile`, `bpm >= 90`, tối đa hai ô liên tiếp: trong tối đa hai ô đó, đoạn chạy thay thế các trùm lặp của bè Cao tremolo, bè Trung nghỉ, bè Trầm chuyển từ ngón cái mỗi nốt đen sang đánh gốc ở phách 1 và 3; mốc dữ liệu neo ở móc kép 0 của mỗi phách, móc kép 2 là nốt chạy, rồi quay về đúng nốt đang giữ.

**Grand Solo của Sor** là bộ biến tấu và nhấn kịch tính phủ lên pattern `study` (chỉ khi `bpm >= 90`, `rally` hoặc `volatile`, từ câu thân thứ hai trở đi; `1D` ở 88 BPM không bật Grand Solo mà giữ `study` thường): hai câu thuộc cùng một họ khi cùng pitch-class gốc ô mở, cùng dấu hướng, đỉnh lệch không quá hai bậc, độ dài lệch không quá bốn móc đơn. Mức figuration trên pattern `study` tăng một bậc khi câu lặp trong họ (`level 0` giữ `study` chuẩn, `level 1` lấp đầy arpeggio các móc yếu, `level 2` phủ thêm đoạn scale đi lên đỉnh khi `phrase.rise >= MIN_RISE` và band `mf`/`f`), đặt lại 0 khi sang section không phải tái hiện. Khung nốt phách mạnh không đổi giữa các lần. Đầu section ở band `f` (trong chương `bpm >= 90`), ô mở của Grand Solo đánh hợp âm khối ba nốt (Trầm + Trung + Cao cùng lúc); trước câu chứa đỉnh cao nhất của section, nếu câu trước đó đóng, cả ba bè được lặng một móc đơn (caesura) tại `phrase_i.end - 1` để lấy hơi kịch tính (caesura này ưu tiên hơn nốt bass bắc cầu của mục 3.2, nên voice 3 cũng nghỉ).

## 9. Điệu — Phase 2

Điệu không đổi `slots` và không đổi ký hiệu nhịp. Ở mọi mẫu điệu (choro 4/4, polca 6/8 thường, và hemiola 6/8), bè Cao (voice 1) luôn hát nguyên vẹn đường giai điệu đã nén trên lưới móc đơn của dữ liệu (mọi móc kép chẵn có nốt dữ liệu mới đều đánh, không bỏ và không dời sang móc khác). Móc lẻ là đệm của Trầm và Trung. Các bảng ở 9.1 và 9.2 là lịch gảy của bè Trầm (voice 3) và bè Trung (voice 2) đặt dưới đường giai điệu đó; ở móc kép chẵn không có trong bảng (như móc kép 2 của choro hay móc kép 2, 8 của polca thường), nếu lưới dữ liệu có nốt mới thì bè Cao vẫn hát một mình. Cụm cùng vang tối đa ba nốt (khi móc kép chẵn có cả Trầm, Trung và Cao thì tỉa theo thứ tự đang có, Trung luôn thấp hơn Cao đang vang), đi qua luật gập bass và thứ tự bè đang có.

Chỉ chọn khi bước 4 của bộ chọn đạt: câu không giữ hai phách, character khác `calm`, `bpm > 100`, meter 4/4 hoặc 6/8. Câu ngân ở scherzo 120 band `f` vẫn là tremolo.

### 9.1. Choro, meter 4/4

`divisions = 4`. Một ô là hai levada tám móc kép. Trong mỗi nửa ô, tính từ đầu nửa đó:

| Móc kép | Bè | Nội dung |
|---|---|---|
| 0 | Trầm + Cao | Gốc. Cao là nốt dữ liệu |
| 3 | Trung | Một âm hợp âm đã tỉa |
| 4 | Trầm + Cao | Quãng 5. Cao là nốt dữ liệu |
| 6 | Trung, và Cao nếu trùng nốt dữ liệu | Âm bảy hoặc âm ba |
| 7 | Trung | Một nốt hợp âm, lệch trước phách sau |

Nửa sau cộng 8. Móc 15, khi gốc ô sau thấp hơn đúng một quãng 5, là một nốt Trầm dẫn bán cung dưới gốc ô sau. Ô không rơi quãng 5 thì móc 15 giữ nốt Trung. Maxixe dùng cùng mẫu, không tách điệu.

Số móc này là đề xuất. Đầu Phase 2 đọc một ô *Choro da Saudade* và sửa bảng nếu lệch.

### 9.2. Polca, meter 6/8

Một ô là 12 móc kép. Bản thường:

| Móc đơn | Móc kép | Bè |
|---|---|---|
| 0 | 0 | Trầm gốc + Cao |
| 1 | 2 | Trung |
| 2 | 4 | Trung, và Cao nếu có nốt dữ liệu |
| 3 | 6 | Trầm quãng 5 + Cao |
| 4 | 8 | Trung |
| 5 | 10 | Trung, và Cao nếu có nốt dữ liệu |

Band `f` là bản khác, không phải polca bị khoét. Đệm chỉ ở móc đơn 0, 2, 4. Đó là hemiola: nhấn 0, 2, 4 như mục 4. Cao vẫn hát nếu lưới dữ liệu có nốt ở móc đơn lẻ. Nốt dẫn bán cung, cùng điều kiện quãng 5, là nốt Trầm mới ở móc kép 11, có ở cả hai bản. Ô không rơi quãng 5 thì móc 11 nghỉ.

Đầu Phase 2 đọc *Danza Paraguaya* và sửa bảng nếu lệch. Profile `barrios_dance` nhận nốt dẫn này. Profile `study` báo lỗi trên cùng nốt đó.

### 9.3. Valse Venezolano / Vals Criollo (`vals`), meter 6/8 — Phase 3

Bật ở Phase 3 cho Barrios khi câu đang chạy (bước 4 của bộ chọn) rơi vào `section.trio` của chương 6/8 (`120, 108 BPM`). Thay vì đánh `polca` hai nhóm chấm dôi đều hoặc `hemiola` ba phách chẵn suốt ô, `vals` tái hiện điệu *Vals Op. 8 No. 3 & 4* của Barrios bằng cách **đan 6/8 ở nửa đầu ô với phách thứ ba của 3/4 ở nửa sau ô** ngay trên cùng meter 6/8:

| Móc đơn | Móc kép | Bè | Nội dung |
|---|---|---|---|
| 0 | 0 | Trầm gốc + Cao | Đầu nhóm chấm thứ nhất (6/8) + nốt dữ liệu |
| 1 | 2 | Trung (+ Cao nếu có nốt dữ liệu) | Âm hợp âm nhẹ sau bass đầu ô |
| 2 | 4 | Trung (+ Cao nếu có nốt dữ liệu) | Âm hợp âm khép nhóm đầu |
| 3 | 6 | Trầm quãng 5 (hoặc bậc 3) + Cao | Nhấn syncopation giữa ô (móc 3 của 6/8) |
| 4 | 8 | Trầm âm hợp âm / bậc đi qua + Trung (+ Cao nếu có) | Phách 3 của 3/4 đè lên nửa sau ô, tạo đà lướt qua vạch nhịp |
| 5 | 10 | Trung (+ Cao nếu có nốt dữ liệu) | Âm hợp âm nhẹ cuối ô; móc kép 11 thêm Trầm dẫn bán cung nếu ô sau rơi đúng một quãng 5 |

Đường giai điệu bè Cao vẫn hát đủ trên mọi móc kép chẵn có nốt dữ liệu mới. Profile kiểm tra dùng chung `barrios_dance` (cho phép bass ở móc đơn `0, 3, 4` và nốt dẫn bán cung ở móc kép `11`).

## 10. Dialect hòa âm

Vỏ `HarmonyDialect` đã có. `dialect_for` trả `COMMON` khi ensemble không nằm trong `DIALECTS`. `color_credit` của `COMMON` là 0. Hợp âm ngoài `extra()` vẫn đi `_borrowed_allowed`. Ô pedal chỉ hợp âm chủ.

### 10.1. Villa — đã code

Khóa bởi `backend/tests/test_villa_dialect.py`. Ba phase không đổi các số này.

Sus và add9 phải có mặt lúc Viterbi chọn, trước `quantize_strong_beats`. `jazz_chord` không chạy trên slot villa. Khoản màu 0.70 chỉ khi đã có hợp âm trước, cùng gốc, một phách mạnh là âm màu, và lần đổi đi từ hợp âm ba cha. 0.60 không giữ được sus trước F ở `rally`. Ô đầu bài và ô khác gốc không được khoản. Âm màu chỉ tính khi gốc đó đang được giữ.

`shares_root` đúng khi cùng `root_step` và `alter`, và một bên là `"suspended"`. Add9 ở nhóm `"major"`, không cần cửa này. `degrees` trên `Chord` để `transpose_chord` viết sus đúng chữ. Quãng 5 vẫn ở `pitches[2]`.

Catalog đã lọc, không gian Đô:

| | Trưởng | Thứ tự nhiên |
|---|---|---|
| sus2 | C, D, F, G, A | C, E♭, F, A♭ |
| sus4 | C, D, E, G, A | C, D, E♭, F, G |
| add9 | C, F, G | `Cm add9`, `Fm add9` |
| 7sus4 | G, D, A, `E7sus4` | C, D, F, G |

Trượt song song chỉ ở trưởng: `Csus2` → `Bbsus2` và `Fsus2` → `Ebsus2` cửa 0.22; `Bbsus2` → `F` và `Ebsus2` → `F` cửa 0.34. Mọi cặp khác có một đầu là hợp âm trượt trưởng trả 0. Ở thứ, `Ebsus2` là sus thuận thang, không thuộc danh sách trượt.

Thứ tự `transition`: hợp âm trượt trưởng; về hợp âm ba cha bằng 0.40; cùng gốc với một màu villa bằng 0.30; rồi cửa `_ROOT_TRANSITIONS` của gốc đích hoặc gốc nguồn; còn lại 0 nếu một đầu thuộc `extra()`, `None` nếu không. `bias` tuyệt đối dưới 0.1, chỉ khi phách mạnh là âm màu, cộng lên sàn 0.08. Không bias nào bù phạt phách mạnh 2.5.

Tỉa: hợp âm bốn nốt bỏ quãng 5 trước. Sus không có âm ba để giữ; quãng 2 hoặc 4 chiếm chỗ âm ba.

### 10.2. Barrios — Phase 2

Hòa âm chức năng. Không sus, không add9. `color_credit` trả 0. Giai điệu thứ trên thứ tự nhiên, trưởng trên Đô trưởng. Fa♯, Rê♭ và Đô♯ không có trong `raw_pitches`; nốt ngoài thang làm `bar_quantization_loss` ném lỗi. Nốt đặc trưng ngoài thang có trong tổng phổ (Napolitaine, Đô♯°7, giảm bảy đi qua ở trưởng) không vào `extra()`.

`DIALECTS` thêm `"barrios"`. `dialect_for("classic")` và symphony vẫn là `COMMON`. Thứ thêm bốn hợp âm. Trưởng không thêm hợp âm; chuỗi át dùng `BORROWED` sẵn có và ba cạnh mới.

| Tên | Nguồn | `root_step`, `alter` | Nốt | Vai |
|---|---|---|---|---|
| `Bb` | `BF` | B, −1 | Si♭–Rê–Fa | ♭VII |
| `Bb7` | `BF7` | B, −1 | Si♭–Rê–Fa–La♭ | ♭VII7 |
| `D7` | `D7` sẵn có | D, 0 | Rê–Fa♯–La–Đô | V/V. Trên thang thứ chỉ Rê và Đô |
| `Ab+6` | mới | A, −1 | La♭–Đô–Mi♭–Fa♯ | sext tăng Đức, vào V |

```python
Chord(
    "Ab+6", "A", KIND_OTHER, "+6", (68, 72, 75, 78),
    alter=-1, degrees=(0, 2, 4, 5),
    tones=((8, "A", -1), (3, "E", -1), (6, "F", 1)),
)
```

`(68, 72, 75, 78)` là La♭4–Đô5–Mi♭5–Fa♯5. Thiếu `degrees`, nốt thứ tư bị viết thành Sol♭. `quality_group` trả `"augmented-sixth"` khi `kind_text == "+6"`, trước nhánh `"major"`. Nhóm này để luật một ô bắt được hợp âm. Rơi vào `"major"` thì La♭ → `Ab+6` thành đổi chất giá 0.50.

Trong `form.py`, điều kiện một ô đang dành cho `"diminished"` (`target_held != 1`) nhận thêm `"augmented-sixth"`, trước nhánh đổi tự thân thành `BORROWED_HOLD_PROB` 0.16. `Ab+6` cùng gốc với La♭, nhánh cùng gốc đòi `target_held == 2`, luật một ô cấm `target_held == 2`, nên `Ab+6` không đi từ La♭ hay La♭maj7 và không đứng hai ô.

`shares_root` trả `False`. `transition` trả số khi một đầu thuộc `extra()` của mode đang chạy, hoặc khi cặp nằm trong ba cạnh chuỗi át trưởng. Không có trong bảng mà một đầu thuộc `extra()` thì trả 0. Trả `0` là cấm cặp chuyển tiếp đó (`weight <= 0` bị vòng lặp `form.py` bỏ qua, không đưa vào `ln`), trừ khi giữ nguyên hợp âm (`prev == curr`) mà chất không phải `"diminished"` hay `"augmented-sixth"` thì `form.py` viết lại thành `BORROWED_HOLD_PROB` 0.16. Cặp khác trả `None`. Bắt buộc có số tường minh vì `Bb` không có hàng trong `_ROOT_TRANSITIONS`, và `D7` thứ trùng `root_step` với ii. Trọng số đưa thẳng vào `−0.6·ln`, không nhân 2. Ô thứ hai của một gốc (`prev_held == 1`, không mở section) vẫn dùng `SECOND_BAR_STAY_COST` 0.15, cạnh không vào giá.

Tỉa bốn nốt: bỏ `pitches[2]`. `Ab+6` còn La♭–Đô–Fa♯. `D7` còn Rê–Fa♯–Đô. `Bb7` còn Si♭–Rê–La♭. Ống sửa Phase 3 phải coi Fa♯ của `Ab+6` là âm được giữ, cùng chỗ với âm 7, không bỏ như nốt lạ. Không gọi `jazz_chord`.

**Cạnh thứ, vòng xuống quãng 5**

| Cặp | Trọng số |
|---|---|
| `Fm` / `Fm7` → `Bb` | 0.42 |
| `Fm` / `Fm7` → `Bb7` | 0.34 |
| `Cm` / `Cm7` → `Bb` | 0.12 |
| `Bb` → `Eb` | 0.42 |
| `Bb` → `Ebmaj7` | 0.26 |
| `Bb7` → `Eb` | 0.50 |
| `Bb7` → `Ebmaj7` | 0.34 |
| `Bb` → `G` | 0.22 |
| `Bb` → `G7` | 0.26 |
| `Bb` → `Bb` | 0.18 |
| `Bb` → `Bb7`, `Bb7` → `Bb` | 0.24 |
| `Bb7` → `Bb7` | 0.14 |

`Cm` → `Fm` giữ 0.26. `Eb` → `Ab` giữ cửa E→A = 0.34. Từ Fa thứ, {Si♭, Rê, Fa} ra `Bb`; thêm La♭ ở phách mạnh thì ra `Bb7`. Ô chỉ Si♭, `prev_held == 1`, ở lại `Bb`. Sau khi `Bb` đã giữ hai ô, ra `G` hoặc `G7`. `sing_leading` cho Sol và Sol7 hát Si♭ với phát xạ 0. Nốt Si tự nhiên trên giai điệu thì lượng tử hóa ném lỗi.

**Khép vòng**

| Cặp | Trọng số |
|---|---|
| `Ab` / `Abmaj7` → `D7` | 0.48 / 0.40 |
| `Dm7b5` → `D7` | 0.40 |
| `D7` → `G` | 0.46 |
| `D7` → `G7` | 0.55 |
| `D7` → `D7` | 0.12 |

Không có hợp âm ba Rê trưởng. Ô {Rê, Đô} ở lần giữ thứ hai ở lại `Dm7b5` (0.15 cộng bias 0.06), vì đổi sang `D7` tốn 0.50 cộng sàn 0.13. Cạnh 0.40 chỉ thắng từ ô thứ ba. Phách mạnh Rê sau La♭ thì `D7` thắng (cửa 0.48, giá khoảng 0.57). Phách mạnh La♭ thì `D7` mất 2.5.

**Sext tăng**

| Cặp | Trọng số |
|---|---|
| `Fm` / `Fm7` → `Ab+6` | 0.24 / 0.20 |
| `Cm` / `Cm7` → `Ab+6` | 0.06 |
| `Ab+6` → `G` | 0.62 |
| `Ab+6` → `G7` | 0.55 |

`Ab+6` vào từ hạ át, giữa câu, khi gốc Fa đã giữ từ hai ô, ô không phải phách đầu câu và không phải pedal, và đường kết tại ô đó hoặc ô sau ngồi trên {Sol, Rê}. Ô thứ hai của gốc Fa thì `Fm7` chứa {La♭, Đô, Mi♭} với giá đổi chất 0.50 và thắng. Ba ô liền toàn {La♭, Đô, Mi♭} không mở sext tăng, vì Sol mất 2.5 ở ô kế. Fa ở phách mạnh của ô sau thì ô đó là `G7`. Không quá ba móc yếu Fa: móc thứ tư, hoặc móc 4 của 3/4 (trọng 0.8), đảo sang `G7`. Cửa từ chủ 0.06 không thắng một ô thuận thang. Không đăng ký `Db` và `C#dim7`.

**Ba cạnh trưởng**

| Cặp | Trọng số |
|---|---|
| `E7` → `A7` | 0.55 |
| `A7` → `D7` | 0.55 |
| `D7` → `G7` | 0.55 |

`A7` → `Dm` vẫn 0.40. `D7` → `G` vẫn 0.46. Phách mạnh Đô, La hoặc Rê thì chuỗi rẻ hơn về thứ khoảng 0.17. Phách mạnh Fa thì về hợp âm thứ. Không khóa bằng Fa♯.

`allowed` trả `True` với hợp âm không thuộc `extra()`. Mọi `extra()` trả `False` ở pedal và ở phách đầu câu. `Bb` được đứng từ ô thứ hai. `bias` cộng thêm, tuyệt đối dưới 0.1: `volatile` trừ 0.06 cho `Bb`, `Bb7`, `D7`; `rally` trừ 0.04 cho `D7` và `Bb7`. Không mức nào bù phạt 2.5, cũng không bù cửa 0.26 vào Fa thứ khi nốt thang đã nằm trong Fa thứ.

Hợp âm `extra()` nhận sàn 0.08, rồi hợp âm bốn nốt cộng 0.05. `Bb` dừng ở 0.08. `Bb7`, `D7`, `Ab+6` thành 0.13. `minor_bias` không chạy cho `extra()`. `root_step` B không có trong bảng bias thứ; gọi thẳng `minor_bias(Bb)` vẫn lỗi, và đường chọn hợp âm không gọi nó. Không sửa `minor_bias`.

## 11. Âm vực và part

Đã code. Bè tính trên cao độ vang; renderer so số viết với biên đã trừ `semitones`.

| Bè | Vang cho phép | Ghi chú |
|---|---|---|
| Trầm | 40–53 | Gập pitch-class vào dải trước khi viết. Ngoại lệ duy nhất ở Phase 3: pattern `thumb_cantabile` (mục 6.5) cho phép voice 3 hát giai điệu ngón cái lên tới vang 64 (`64 − semitones` viết) dưới profile `thumb_cantabile` |
| Trung | 50–65 | Khối ở vùng cao, Phase 3, được vượt 65 nếu còn trong thế tay với giai điệu |
| Cao | 59–81 | Trần đường giá 81. Vang 82–83 chỉ cho chuông Preludio, Phase 3 |
| Trần cứng | 83 | |

Ba voice: Cao 1, Trung 2, Trầm 3. Khi cùng vang, Trầm thấp hơn Trung, Trung thấp hơn Cao. Tremolo được xếp gốc và quãng 5 trong cùng voice Trầm. Part, giọng Muse và transpose đã khóa trong `musicxml.py` và `audio.py`.

Phase 3 thêm mô hình dây (dây 6→1 buông ở 40, 45, 50, 55, 59, 64), giới hạn phím theo dây (dây 6–4 nhận phím 0–12, dây 3 nhận 0–17, dây 2–1 nhận 0–19), khoảng phím ≤ 5 trên các nốt bấm cho cụm cùng vang (dây buông phím 0 không tính vào khoảng phím), và khoảng phím ≤ 5 theo từng thế bốn móc kép cho đoạn scale. `assert_playable` chỉ báo, không sửa. Profile theo pattern đang chạy: `study`, `grand`, `elegiaque`, `cantabile` (cho phép bè Trung đi song thanh quãng 3/6 cùng tiết tấu với bè Cao), `villa_pattern`, `villa_chord`, `thumb_cantabile` (cho phép voice 3 hát đường giai điệu tới vang 64 và voice 1–2 chập phách yếu phía trên), `barrios_preludio` (cho phép nốt chuông ở bè Cao lên tới vang 83 / `guitar_ceiling`), `barrios_tremolo`, `barrios_chorale`, `barrios_dance` (gồm cả `choro`, `polca`, `hemiola`, `vals`), `barrios_run`. Luật bass và trần riêng của profile này không áp cho profile khác.

## 12. Test theo phase

**Đã có, giữ nguyên:** một part nylon; BPM 88 / 100 / 120; biên viết dịch hai chiều; hoán meter và cờ `trio`; nén câu không đảo hướng; tremolo đầy ở 4/4 và ở scherzo 6/8; ngón cái 58 giữ gốc, quãng 5 cùng trùm; chương 60 BPM không tremolo và không tăng tempo; dialect Villa và `dialect_for("barrios")` còn `COMMON`; ép ngón hiếm, không ở câu đầu.

**Phase 1**, trong `test_sonify_guitar.py` (ở các test tại `bpm >= 90` như 1, 2, 5, 6, 8, câu cần kiểm tra tremolo hoặc thánh ca đặt từ **câu thân thứ hai trở đi**, vì câu thân đầu chương ở `bpm >= 90` luôn là arpeggio theo bước 1):

1. 120 BPM, từ câu thân thứ hai, giai điệu giữ từ hai phách, band `mf`: tremolo đầy trên câu không đóng (`closes=False`) khi câu kế tiếp vẫn là tremolo, hoặc trên câu ngắn hơn bốn phách đen (như một câu đóng dài đúng một ô 6/8 = 3 phách đen); riêng câu đóng (`closes=True`) hoặc câu tremolo ngay trước khi đổi sang pattern khác mà dài từ **bốn phách đen trở lên** (≥ 8 móc đơn, phần trước còn ít nhất hai phách tremolo) thì hai phách đen cuối tắt tremolo về arpeggio kết, và khi đổi pattern sang câu sau thì móc đơn cuối `phrase.end - 1` của bè Cao và bè Trung nghỉ lấy hơi (mục 3.2). 6/8 vẫn ba trùm nốt đen, mọi móc kép hát.
2. 120 BPM, từ câu thân thứ hai, giai điệu đổi từng móc đơn: arpeggio, không tremolo, không dance.
3. Ô `_PEDAL` (`intro`, `outro`, `warmup`, `cooldown`) ở 120: giữ pedal (bass gốc ngân cả ô, không tremolo); câu thân đầu chương ở 120 (kể cả khi giữ nốt): arpeggio, không tremolo.
4. 72, 60 hoặc 66 BPM, 3/4: cả thân chương (kể cả câu thân đầu) là thánh ca của nhà đó, BPM không đổi, không một trùm tremolo.
5. Barrios, câu tremolo thứ ba liên tiếp (sau hai câu tremolo ở thân bài): thánh ca `andante` theo lưới mục 6.1, trên cùng `Score.divisions = 4` của chương.
6. Sor, chương chậm (`bpm <= 72`, kể cả câu đầu), hoặc `1D` 88 BPM khi `selloff` (kể cả câu đầu), hoặc chương `bpm >= 90` từ câu thân thứ hai khi `selloff` hay ở `section.trio` mode thứ: bass đúng mẫu chấm của meter đó; riêng chương `bpm >= 90` khi `selloff`, câu thân đầu vẫn là arpeggio. Appoggiatura giải về đúng nốt dữ liệu theo hướng bước kế tiếp, tối đa một mỗi câu.
7. Villa `chord_melody`: ở chương chậm 3/4, ba bè cùng onset ở móc 0, thêm khối ở móc 4 tại các ô từ đầu câu tới ô `phrase.apex` (khi `phrase.rise >= MIN_RISE`), tại ô `phrase.apex`, hoặc tại ô kết câu đóng, và không ô nào có khối ở móc 2; ở 6/8 (như scherzo `calm` từ câu thân thứ hai), ô thường chỉ đánh khối ở móc 0, riêng ô chứa `phrase.apex` và ô ngay trước nó trong câu có `phrase.rise >= MIN_RISE` đánh khối ở cả móc 0 và móc 3, không có khối ở móc 1, 2, 4, 5; ở 4/4, khi `phrase.rise >= MIN_RISE`, các ô từ đầu câu tới ô `phrase.apex` dồn từ móc `0, 4` thành `0, 2, 4, 6`.
8. `calm` ở 6/8, 120, band `f`, từ câu thân thứ hai có giai điệu giữ nốt: tremolo, không hemiola. Câu thân đầu của cùng chương vẫn là arpeggio.

**Phase 2**, harmony trong `test_harmony.py`, điệu trong `test_sonify_guitar.py` (các test điệu và tremolo ở `bpm > 100` như 8, 9, 10 kiểm tra từ **câu thân thứ hai trở đi**, vì câu thân đầu chương luôn là arpeggio theo bước 1):

1. `dialect_for("barrios")` là `BarriosDialect`. `classic` và symphony ở thứ không sinh `Bb`, `Ab+6`, `D7`. `extra()` thứ đúng bốn tên. `extra()` trưởng rỗng. Villa vẫn sinh `Csus4` đúng các ca đã khóa.
2. Sàn `extra()`: `Bb` 0.08; `Bb7`, `D7`, `Ab+6` 0.13. Không test gọi `minor_bias(Bb)`.
3. Thứ, sau `Fm`, phách mạnh trong {Si♭, Rê, Fa}: `Bb`. Thêm La♭: `Bb7`.
4. Thứ, sau `Ab`, phách mạnh Rê, móc khác trong {Rê, Đô}: `D7`. Phách mạnh La♭: không `D7`.
5. Thứ, {La♭, Đô, Mi♭}, giữa câu, gốc Fa đã giữ từ hai ô, ô sau trên {Sol, Rê} hoặc đường kết tại ô này: `Ab+6`. Ô thứ hai của gốc Fa: `Fm7`. Ô mở section: không `Ab+6`. `Ab+6` không đi từ `Ab` và không đứng hai ô. Ô sau là `G` hoặc `G7`.
6. Trưởng, sau `A7`, phách mạnh Đô, La hoặc Rê: `D7`. Phách mạnh Fa: `Dm` hoặc `Dm7`.
7. `color_credit` Barrios là 0. `transpose_chord` của `Ab+6` giữ Fa♯.
8. 4/4, `bpm > 100`, từ câu thân thứ hai, câu nốt chạy, `rally`: dance (câu thân đầu vẫn là arpeggio), đúng các móc đã khóa sau khi đọc tổng phổ. Mọi nốt Cao trên móc kép chẵn trùng nốt dữ liệu (kể cả móc kép 2 nếu dữ liệu có nốt mới). `calm`: không dance. 3/4: không dance. 100 BPM: không dance.
9. 6/8, 120, từ câu thân thứ hai, band `mp`, câu ngân: tremolo, không polca (câu thân đầu vẫn là arpeggio). Cùng tempo, từ câu thân thứ hai, band `f`, câu nốt chạy: hemiola, đệm chỉ móc kép 0, 4, 8. Cùng tempo, từ câu thân thứ hai, band `f`, câu ngân: tremolo.
10. Ô dance (từ câu thân thứ hai) rơi đúng một quãng 5 khi câu vẫn đang ở dance: 4/4 móc kép 15, 6/8 móc kép 11, là Trầm nửa cung dưới gốc sau; nếu ô đó là cuối câu mà câu kế tiếp đổi sang pattern không phải dance thì móc kép cuối nghỉ và móc đơn cuối câu nhường khe thở theo mục 3.2. Profile `study` báo lỗi trên nốt dẫn; `barrios_dance` im.

**Phase 3:** nốt đích của scale trùng nốt dữ liệu; nốt đầu được lệch và test không đòi nó trùng dữ liệu; phách mạnh trong đoạn giữ cao độ; ô perpetual thay trùm lặp bè Cao của tremolo trong tối đa hai ô và chuyển bass về phách 1 và 3; không section nào quá khoảng 15% ô chạy; Grand Solo (chỉ ở `bpm >= 90`, từ câu thân thứ hai) ở band `f` mở section bằng hợp âm khối ba nốt và có khoảng lặng một móc đơn (caesura) ở cả ba bè (kể cả bè Trầm, không đánh bass bắc cầu) trước câu đỉnh khi câu trước đó đóng; Sor `calm` ở `bpm > 72` chạy `cantabile` với bè Trung đi song song quãng 3 hoặc quãng 6 thuận thang dưới bè Cao (từ câu đầu ở 88 BPM, từ câu thân thứ hai ở `bpm >= 90`); `thumb_cantabile` (của Villa ở `section.trio` / `section.bridge`; của Barrios ở `section.bridge` của chương dưới 90 BPM, hoặc ở câu nghỉ sau hai câu tremolo trong `section.trio`, hoặc câu chạy `calm` trong `section.trio`; không bật ở `1D`, `1W` hay chương 4/4) dịch + nén đơn điệu đường giá xuống voice 3 (vang trọn trong 48–64 kể cả khi câu gốc rộng hơn 16 nửa cung, đơn điệu cùng hướng câu gốc) và chỉ đánh hợp âm voice 1–2 ở phách yếu (móc `2, 4` ở 3/4; móc `2, 5` ở 6/8; móc `2, 6` ở 4/4); Barrios câu chạy (khác `calm`) ở `section.trio` của 6/8 chạy `vals` với bass ở móc đơn `0, 3, 4`, còn câu ngân ở `section.trio` 6/8 vẫn là `tremolo`; chuông Preludio tính bằng `bell_budget`, tách khỏi hạn một nốt mỗi hai ô, được phép tới vang 83 dưới profile `barrios_preludio`; cụm cùng vang gán được dây (dây 6–4 ≤ 12, dây 3 ≤ 17, dây 2–1 ≤ 19), khoảng phím ≤ 5, trừ ngoại lệ tremolo đã khóa; bass Élégiaque, giai điệu Trầm của `thumb_cantabile`, và nốt dẫn của Villa hoặc của `barrios_dance` đạt ở đúng profile và lỗi ở `study`.

## 13. Nghe

Phase 1: `1D` Barrios, câu thân đầu vẫn là arpeggio; từ câu thân thứ hai, câu ngân thì tremolo liền, bass đầu mỗi nốt đen, còn câu nốt ngắn vẫn arpeggio; chỗ chuyển từ tremolo sang `andante` hoặc arpeggio có giảm tốc hai phách cuối và khe thở một móc đơn tự nhiên, không bị cắt dán đột ngột. Chương chậm 3/4 của cả ba nhà hát hợp âm ngay từ câu đầu, không tremolo, không bị kéo nhanh. Sor `selloff` nghe ra bass chấm (ở `1D` 88 BPM nghe ngay từ câu đầu; ở chương `bpm >= 90` nghe từ câu thân thứ hai). Mở bài Barrios chưa cần chuông.

Phase 2: phiên thứ, ô {Si♭, Rê, Fa} sau Fa thứ là một ô Si♭ rồi đi tiếp, không có ô Rê♭. Chuỗi át đi tiếp khi giá trên Đô, La hoặc Rê, và về thứ khi giá trên Fa. `1D` từ câu thân thứ hai, câu chạy ở `rally` có đệm bass và Trung lệch phách kiểu choro bên dưới giai điệu giá giữ nguyên trên lưới móc đơn; câu ngân không bị levada cắt. Scherzo band `f` chỉ nghe hemiola khi giai điệu đang chạy (sau câu mở). `calm` không dày hơn Phase 1.

Phase 3: đoạn chạy rơi đúng phách mạnh, rồi còn nhận ra đường giá. Mở bài Barrios chạy pattern `preludio` (bass mỗi hai ô, có chuông khi phiên có biên độ) và nhường câu sau cho tremolo/choro. Vòng `villa_pattern` không che nốt Cao. Sor `calm` nghe hai bè hát song thanh quãng 3/6; đoạn giữa `trio` của Villa/Barrios nghe tiếng ngón cái hát trầm như Cello với hợp âm đáp ở phách yếu, hoặc nghe nhịp *Vals* đan 6/8–3/4 khi câu chạy. Lần lặp Grand Solo trên nền `study` nghe dày hơn, khung phách mạnh vẫn là khung cũ.
