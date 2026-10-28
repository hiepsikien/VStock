# Điều Chỉnh Biên Độ Scale Theo Thể Loại

> **Trạng thái**: đề xuất, chưa viết vào engine.
> **Tài liệu liên kết**: [`docs/sonify-guitar-scales-plan.md`](./sonify-guitar-scales-plan.md) Mục 2.6, [`docs/sonify-guitar-bach-suite-plan.md`](./sonify-guitar-bach-suite-plan.md).
> **Mục tiêu**: câu scale vẫn là một hairpin một chiều. Brouwer giữ Mục 2.6.C. Các hàng thu hẹp đo từ velocity bè cao sau sóng volume, với bước vào, biên độ và trần khóa theo id pattern.

---

## 1. Chỗ đang gắt

Ô 27 của Prelude trong MSN 1W Bach (Guitar, 22–28/10/2026) là mẫu. Vùng quanh ô đang ở velocity khoảng 45–56. Ramp tuyến tính của cửa Baroque `54…84` in tám móc kép `84, 80, 75, 71, 67, 63, 58, 54`. Đó là hai phách. Nốt trụ đứng sau ramp bị sàn `_BASS + 2` kéo lên `62`. Tính cả nốt trụ thì cụm đó là chín móc kép.

`restamp_passage_hairpins` cố ý đọc `written_lead`, tức velocity trước `apply_guitar_wave`. Sóng xuống của Hát và Baroque là

```text
open = min(loud, max(prev + 8, 72))
```

`prev` trước sóng từ `76` trở lên thì mở tại trần `84`. Lần trace của ô này cho `prev = 76`. Dãy velocity chứng minh cửa và sàn trụ, và chứng minh `prev` trước sóng đạt ngưỡng `76`. Sóng volume đã kéo vùng quanh ô về khoảng `45…56`, rồi hairpin in lại đè lên. Nếu nốt tai vừa nghe là `56`, cú nhảy lên `84` là `+28`, tức ba bậc rưỡi nhấn (`3 × 8 = 24`).

`_LOUD_DOWN_PATTERNS` mở sóng xuống tại `loud` trên phách mạnh. Nhóm Động năng mở tại `90`. `bach_chaconne` mở tại `88`. `elogio_pizz` tách khỏi étude: cửa `44…92`, étude Brouwer là `46…90`.

`bach_courante` không nằm trong `_HAT_PATTERNS` hay `_BAROQUE_PATTERNS`. `_base_window` trả cửa mặc định Hát `52…82`. `bach_allemande` đang ở `_HAT_PATTERNS`, cũng `52…82`. Prelude đang ở `_BAROQUE_PATTERNS`, cửa `54…84`.

## 2. Hai nguồn `prev`

Brouwer đang nghe ổn, nên passage và swarm của Brouwer vẫn đọc nốt lead trước sóng. `_restamp_swarm_hairpins` tiếp tục nhận `written_lead`. Sóng lên của Brouwer giữ subito piano ở Mục 2.6.C: `open = min(prev, soft)`, và rơi xuống `soft` khi `prev ≥ 72`. Elogio giữ cùng mục đó, kể cả mở tại trần khi đi xuống trên phách mạnh.

Các hàng thu hẹp đọc nốt lead **sau** `apply_guitar_wave`, trên `lead` đang bị ghi đè. `restamp_passage_hairpins` đi `plan.passages` rồi `plan.tier1`. Câu sau thấy hairpin vừa in của câu trước, không đọc lại `written_lead`. Gọi mức đó là `heard`. Sóng volume đã mang band của ô, nên các hàng này không cộng `_HAIRPIN_SHIFT` thêm một lần. Band `f` là `+4`. Cộng vào trần prelude `72` thành `76`. Band `p` là `−8`. Trừ lần nữa trên `heard` là trừ piano hai lần.

## 3. Mức theo composer và pattern

Cửa của một passage vẫn là pattern chiếm nhiều eighth nhất trong `[passage.start, passage.target)`, hòa thì lấy pattern tại `passage.start`, như Mục 2.6.A. Passage mở ở prelude nhưng nằm dài hơn trên allemande nhận hàng vũ điệu Bach, không nhận `+2 / 6 / 72`.

Cửa sổ khóa theo id pattern, không theo ensemble. `thumb_cantabile` dùng chung Villa và Barrios, nên một id một mức: hàng Villa.

### Giữ Mục 2.6.C

`prev` là nốt trước sóng. Sàn nốt trụ vẫn là `max(soft, _BASS + 2)`, không dưới `62`.

| Composer | Pattern | Cửa hiện tại | Sóng xuống trên phách mạnh |
|---|---|---|---|
| Brouwer | `sarabande`, `noviembre` | Hát `52…82`, span 30 | `open = min(loud, max(prev + 8, 72))` |
| Brouwer | `brouwer_etude` | Động năng `46…90`, span 44 | mở tại trần |
| Brouwer | `elogio_pizz` | `44…92`, span 48 | mở tại trần |

Trần ở đây là `loud` sau `_HAIRPIN_SHIFT`. Band `mf` mở étude tại `90` và Elogio tại `92`. Band `p` dịch `loud` xuống `8`, nên hai cửa đó mở tại `82` và `84`.

### Hàng thu hẹp

`heard` là velocity lead đang bị ghi đè. Affine của sóng volume không kéo nốt mềm lên sàn cửa sổ. Prelude có sàn `28…34`, nên `heard` có thể ở khoảng `30`.

- Xuống: `open = min(trần, max(40, heard + bước vào))`. Đích = `min(open, max(40, open − biên độ))`. Sàn `40` khóa hai đầu của câu đi xuống. Đích không cao hơn `open`.
- Lên: `open = min(trần, heard)`. Không rơi xuống `soft`. Đích = `min(trần, open + biên độ)`. Sàn `40` không kéo điểm mở của câu đi lên.
- Nốt trụ là đích của ramp. Không kéo lên `_BASS + 2`.

`heard = 30` và prelude đi xuống thì đứng yên tại `40`. Cùng nốt đó đi lên thì mở tại `30` và lên `36`. `heard = 40` đi xuống vẫn là `42 → 40`. `heard = 56` đi xuống vẫn là `58 → 52`.

Nhịp `retreat` của Mục 2.6.C vẫn chùng `3` bậc ngược chiều hairpin. Brouwer và Elogio kẹp trong `[soft, loud]`. Hàng thu hẹp không còn cặp đó. Kẹp trong khoảng hai đầu ramp, sau khi đã áp sàn và trần: từ `min(open, đích)` tới `max(open, đích)`. Kẹp theo `[40, trần]` thì prelude `58 → 52` gặp `+3` thành `61`, vượt biên độ `6`.

`v_ceil` của affine không quá `63`. Bước vào không quá `+6`, nên một câu đi xuống đứng riêng sau sóng mở tối đa `69`, thấp hơn trần thấp nhất `72`. Trần bắt đầu có việc khi nốt liền trước là snap (`choro`, `hemiola`, `etude11` tới `74`) hoặc là đích của passage vừa in trong cùng vòng `restamp`. Ô 27 nhỏ lại nhờ `+2` và biên độ `6`.

Sóng lên cũng kẹp điểm mở. Passage Chaconne có thể kết tại `80`. Passage prelude ngay sau đọc đúng nốt đó: `open = min(72, 80) = 72`, đích = `min(72, 78) = 72`. Không mở tại `80` rồi đi xuống `72`.

| Composer | Pattern | Bước vào khi đi xuống | Biên độ | Trần |
|---|---|---:|---:|---:|
| Villa | `villa_pattern`, `etude1`, `etude11`, `chord_melody`, `thumb_cantabile` | +6 | 24 | 80 |
| Barrios | `preludio`, `andante`, `tremolo`, `choro`, `vals`, `polca`, `hemiola` | +4 | 18 | 76 |
| Sor | `study`, `galop`, `mozart_var`, `cantabile`, `elegiaque` | +4 | 16 | 76 |
| Bach | `bach_sarabande`, `bach_fuga`, `bach_allemande`, `bach_courante`, `bach_bourree`, `bach_gavotte`, `bach_gigue` | +4 | 12 | 74 |
| Bach | `bach_chaconne` | +6 | 18 | 80 |
| Bach | `bach_prelude` | +2 | 6 | 72 |

`choro`, `vals`, `polca`, `hemiola` là `barrios_dance`. Hôm nay chúng thuộc `_KINETIC_PATTERNS` và mở sóng xuống tại `90`. Hàng Barrios `+4 / 18 / 76` rộng hơn hàng Sor `+4 / 16 / 76`.

`etude1` và `etude11` là Villa. `study` là Sor. `brouwer_etude` ở bảng giữ nguyên. `elegiaque` và `cantabile` là Sor, hôm nay ở cửa Hát. `mozart_var` là Sor, hôm nay ở Động năng. `bach_chaconne` bỏ sforzando tại `88`. Mức `+6 / 18 / 80` là đoạn hùng biện, rộng hơn vũ điệu Bach và hẹp hơn cửa `52…88`.

`tremolo` hôm nay không có tên trong `_base_window`, nên rơi cửa mặc định Hát `52…82`. Bảng này đặt nó vào hàng Barrios để không rộng hơn `preludio`.

## 4. Ô 27 sau khi chỉnh

Công thức prelude đi xuống: `open = min(72, max(40, heard + 2))`, đích = `min(open, max(40, open − 6))`.

Nốt lead ô 26 đang nghe là `56` thì ô 27 mở tại `58` và về `52`. Nốt đó là `45` thì mở tại `47` và về `41`. Cả hai đều ở cùng vùng với ô đứng trước. Không còn đỉnh `84` và không còn nốt trụ `62`.

## 5. Phần không đổi và test phải viết lại

Đường cao độ, ngân sách 30%, cửa sổ tirata, và chỗ bass nghỉ của Courante và Allemande giữ nguyên. Hairpin vẫn chỉ ở bè cao. Bass và bè giữa giữ mức của pattern.

`hairpin_velocities` nhận `prev` trực tiếp. Sửa riêng `restamp_passage_hairpins` không đổi các test gọi hàm đó với `prev` cũ. Prelude hôm nay là cửa `54…84`, không phải `52…84`.

Khi viết engine, các khóa sau đổi theo bảng Mục 3:

- Bourrée mở tại `72` theo công thức Hát/Baroque cũ.
- `study` mở tại `90`, `bach_chaconne` mở tại `88`, khi đi xuống trên phách mạnh.
- Render `villa_pattern` mở tại `90` và nốt trụ tại `_BASS + 2`.
- `elegiaque` mở tại `72`.
- Swarm Brouwer `sarabande` vẫn mở từ `written_lead`.
