# Torroba: Juglar bass, ô đệm A–B–A, động lực A đầu, và tempo 92–132

> **Trạng thái**: **đã vào code**, `SPAN_REVISION` `"70"` → `"71"`, `pytest tests/ -q` **751 passed**. Đo lại trên ACB 1M II: bass đủ `1,0` phách ở mọi phách (bar 47/49 không còn `0,5`), ô đệm rơi đúng **bar 46** (ô Castillo cuối cùng) và **bar 69**, cả hai đường framed/unframed đều có gap `2,0–3,0`.
> **Lệch so với kế hoạch ban đầu**: mối nối A→B không phải bar 48 mà là **bar 46**. Phrase Castillo cuối vùng (phrase 15) trải tới hết bar 46, còn section B bắt đầu ở bar 46; nên bar 46 vẫn render `castillo`, và đó mới là ô cuối vùng đi trước. Vì vậy `_torroba_boundary()` đọc **hai bar liền kề** (`_bar_pattern(bar) != _bar_pattern(bar+1)`) thay vì đọc `ctx.section()`/`section.end - 1`, và `apply_sonatina_downbeats()` bỏ pickup khi bar trước là ô đệm để gap không bị lấp lại.
> **Đọc cùng**: [`docs/sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md), [`docs/sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md), [`docs/sonify-guitar-torroba-tempo-plan.md`](./sonify-guitar-torroba-tempo-plan.md), [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md).
> **Giữ**: không thêm id pattern, không thêm ô nhạc, không đổi form A–B–A, không đổi cờ `bridge` / `trio` trong `span.py`. Chỉ sửa nội dung bên trong ô đã có.

Bốn việc cùng một đợt, đo trên đúng bản **ACB 1M chương II** (3/4, 96 BPM, `Castillo — Juglar — Castillo`, 108 ô):

1. **Juglar tremolo**: bass đủ nốt đen ở cả ba phách, không được mất; nốt cao thứ 4 của chùm là móc đơn, riêng chùm cuối ô là móc kép.
2. **A–B–A**: ô cuối vùng đi trước thành **ô đệm** thật, có khoảng trống rõ, không tắt phụt.
3. **Castillos A đầu**: đường cong động lực rõ, nốt lặp không còn cùng velocity.
4. **Tempo**: hạ trung bình khoảng 8 BPM, sàn **92**, trần **132**.

---

## 0. Hiện trạng đo được

### 0.1. Juglar

Mỗi phách hiện là một chùm `p-a-m-i`: bass ở đầu phách, ba ngón cao ở `+0,25 / +0,50 / +0,75`, cả ba ngón đều dài `0,25` phách. Bass đi qua `_sounding_bass` → `_torroba_bass`, nhưng `_sounding_bass` **chỉ nhận dây buông** `40 / 45 / 50`.

Điểm cần nói rõ: ACB 1M II ở giọng **Si♭** (`ctx.semitones = -2`), nên dây buông trong hệ **written** là `42 / 47 / 52`, không phải `40 / 45 / 50`. Hợp âm F written có pitch classes `F A C = {5, 9, 0}`; không âm nào trong `42 / 47 / 52` rơi vào tập đó. Vì vậy `_torroba_bass()` trả **`45`** (âm A viết, bấm), nhưng `_open_bass_tone(ctx, 45)` kiểm `45 + (-2) = 43`, không phải dây buông → `False`; `_sounding_bass()` trả `None`.

Đo trực tiếp (`backend/tmp/diag_juglar_bass_why.py`) trên bar 58/59/64:

```text
chord=F  sung=69/72  _torroba_bass=45  _open_bass_tone(45)=False
_sounding_bass=None   _fitting_bass(lengths=(2,))=45  _chord_bass_at=45
```

Tức lỗi nằm ở **tầng lọc dây buông**, không phải ở cửa sổ bass: `_fitting_bass()` đã tìm được bass `45` dài đủ 2 móc. Vì vậy chỉ cần bỏ lọc `_sounding_bass` cho Juglar là bar 58/59/64 có lại bass; không cần hạ lead hay đổi cửa sổ.

Đo trên ACB 1M II:

| Ô | Hiện tượng |
|---|---|
| 58, 59, 64 | **mất bass cả 3 phách** (hợp âm F; `_torroba_bass=45` bị `_sounding_bass` loại) |
| 47, 49, 56 | bass phách 3 chỉ còn `0,5` phách |
| 69 | ô cuối vùng: 3 nốt đen, nốt cao cuối dài `1,0`, ngân sát vạch nhịp |

Nguyên nhân thứ hai: `_fitting_bass(..., lengths=(2, 1))` ưu tiên 2 móc, nhưng khi chỉ 1 móc vừa tay thì nó ghi `0,5` phách; khi không móc nào vừa thì trả `None` và caller `continue` — tức bỏ luôn cú bass.

### 0.2. Transition

Đo lại bằng `backend/tmp/diag_transitions.py` và `backend/tmp/diag_frame_path.py`: trên ACB 1M II, **đường render thật của app là framed**, nên `_smooth_boundaries()` chạy, không phải `_transitions()`. Cả hai đường đều **không tạo khoảng trống** ở bar 48/69:

- `_smooth_boundaries()` bỏ qua bar 48/69 vì chúng nằm trong `owned` (figure plan của Torroba).
- `_transitions()` (đường unframed) cũng không gọi `_silence` cho hai bar này: nhánh `_silence` chỉ chạy khi câu kết thúc `held_ending`, và `different_family` của Torroba→Torroba là `False`.

Vì vậy hiện tại **không có ô đệm, cũng không có khoảng trống chủ động**: bar 48 chạy tới `2,75`, bar 69 ngân tới vạch nhịp rồi pattern kế vào ngay.

Nếu nhánh `_silence` có chạy (ví dụ câu kết thúc held ở ensemble khác), nó cắt đúng **móc cuối** bằng `_drop_overlap`, tức cắt ngang nốt đang ngân. Kế hoạch dưới đây thay cả hai trường hợp bằng một ô đệm chủ động, dùng chung một helper cho **cả hai đường** `_smooth_boundaries()` và `_transitions()`.

### 0.3. Castillos A đầu

Velocity **trước sóng** đã phẳng, không phải sóng làm phẳng:

| Ô | Trước sóng | Sau sóng (đang nghe) |
|---|---|---|
| 11 | `72 / 72 / 72` | `56 / 56 / 56` |
| 15 | `72 / 72 / 72` | `53 / 53 / 53` |
| 28 | `72 / 72 / 72 / 72` | `52 / 52 / 52 / 52` |
| 45 | `75 / 72 / 73 / 72 / 73` | `58 / 58 / 58 / 58 / 58` |
| 14 | `69 / 69 / ...` | `50 / 50 / ...` |
| 17 | `76 / 72 / 72 / 72 / ...` | `58 / 54 / 54 / 54 / ...` |

Ba nguyên nhân:

1. `_Pen._local_lead()` kéo mọi velocity viết về `lead_level()` của đúng eighth đó, nên một contour đặt **bên trong figure** bị ghi đè. Cơ chế này **không riêng Castillos**: nó chạy cho mọi figure render qua `_Pen` — type 1–8, type 13, type 14 — tức `castillo`, `sonatina`, `fandanguillo`, `danza`, và các bar figure còn lại của `torroba_tremolo` / `alcaniz` / `olite` khi rơi vào `_castillo_spans`. Các figure đặc biệt `JUGLAR_THIN`, `ALCANIZ_OPENING`, `ALCANIZ_SOFT`, `OLITE_THIN` và mọi bar không nằm trong `torroba_figure_plan` đi qua `_render_*_bar`, không gọi `_Pen.add`, nên không bị. Vì vậy contour của kế hoạch phải đặt **sau `apply_torroba_sung_arch`**, ngoài `_Pen`, mới an toàn cho mọi pattern.
2. `_realize()` chỉ cho lead rơi tối đa `steps * _MICRO` (`_MICRO = 2`), và `_micro_fits()` trả `0` khi bass/support đã sát.
3. `apply_guitar_wave()` là **dịch đều một center cho cả ô**, nên nó giữ nguyên chênh lệch viết; chênh lệch 0 vẫn ra 0. Trần `v_ceil = 58` chỉ cắt phần trên, không tạo chênh lệch.

Kết luận: phải tạo contour ở **lớp velocity viết, sau `apply_torroba_sung_arch` và trước `apply_guitar_wave`**. Sóng dịch đều nên contour sẽ sống tới audio.

### 0.4. Tempo

Bảng hiện tại: sàn `96`, trần `140`. `retarget_torroba_tempo()` chỉ nâng tới sàn và cắt ở trần, không hạ chương đã nhanh hơn sàn. Chương 3/4 calm đang ở `96` sẽ **không đổi** khi sàn mới là `92`.

---

## 1. Juglar tremolo

### 1.1. Bass: đủ nốt đen, không bao giờ mất

**Luật**

- Mỗi phách có đúng một cú bass, ngân **`1,0` phách** (`2` móc).
- Bass được phép là **dây bấm**, không chỉ dây buông.
- Khi thế tay xung đột: đổi cao độ bass → chọn âm hợp âm khác → chỉnh voicing bè cao. **Không bỏ cú bass.**

**Cách làm**

Thêm helper trong `guitar_torroba.py`:

```python
def _juglar_bass(ctx, bar, eighth, raw, lead, support) -> tuple[int, int] | None:
    """Bass của một cú p-a-m-i. Dây bấm cũng hợp lệ, và cú bass luôn có mặt."""
```

`lead` được truyền **nguyên list** (không copy) để nhánh hạ voicing ghi thẳng cao độ mới vào chùm; caller giữ list đó khi dựng `low`.

Thứ tự thử (giữ đúng thứ tự ưu tiên, không lặp logic lung tung):

1. `_fitting_bass(ctx, bar, eighth, raw, events, (2,))` — `raw` là `_torroba_bass()`. Hàm này tự thử `raw` trước, rồi `_chord_bass_at()` nếu `raw` không vừa. Đây là bước chính và đã đủ cho toàn bộ ACB 1M II (diag báo `0` lỗi).
2. Nếu bước 1 trả `None`: **hạ voicing bè cao xuống một quãng tám** cho chùm đó rồi thử lại bước 1. Đây là nhánh “chỉnh voicing” đúng ý người dùng, không phải hạ bass.
3. Nếu vẫn `None`: `_fitting_bass(..., (1,))` — giữ cú bass nửa phách còn hơn mất phách. Chỉ dùng khi tay thật sự không giữ nổi 2 móc; ghi log/đếm trong test.
4. Lưới an toàn cuối: thử lần lượt từng âm hợp âm trong `_bass_window(ctx)` ở nửa phách. Nếu **không âm nào** vừa tay kể cả sau khi hạ voicing, trả `None` để caller bỏ phách — thà mất một phách còn hơn ghi nốt không bấm được và làm `assert_playable` fail. **Không xảy ra trên dữ liệu hiện tại** (diag `0` lỗi), nhưng phải đo lại **sau pipeline đầy đủ** để chắc `_repair` / `_resolve` không xóa cú bass.

`_render_juglar_bar()` bỏ hẳn điều kiện `if bass is not None` ở **nhánh chùm tremolo**; mỗi phách gọi `_juglar_bass()` và ghi `low.append(...)`. Nhánh `quarter_notes` (ô cuối vùng, không phải tremolo) giữ một cú bass như hiện tại; nó thuộc mục 1.3, không chịu luật “mỗi phách một cú”.

Vì `_fitting_bass()` đã tự thử `_chord_bass_at()`, test phải khẳng định **cùng phách, cùng cao độ mong đợi hoặc âm hợp âm hợp lệ**, không khẳng định cứng một pitch duy nhất. Riêng bar 58/59/64, pitch kỳ vọng là `45` vì đó là âm bass thấp nhất vừa tay.

### 1.2. Nốt cao thứ 4 của chùm

| Vị trí | Hiện tại | Sau |
|---|---:|---:|
| ngón 1 (`+0,25`) | `0,25` | `0,25` |
| ngón 2 (`+0,50`) | `0,25` | `0,25` |
| ngón 3 (`+0,75`) | `0,25` | **`0,5`** (móc đơn) |
| ngón 3, **chùm cuối ô** | `0,25` | `0,25` (móc kép) |

Nốt thứ 4 dài `0,5` sẽ ngân từ `+0,75` tới `+1,25`, tức nối sang phách sau. Với chùm cuối ô, `+0,75` cộng `0,5` sẽ vượt vạch nhịp, nên giữ `0,25` để kết thúc đúng `3,0`.

### 1.3. Ô cuối vùng Juglar

Ô cuối vùng đang là 3 nốt đen. Nốt cao cuối cùng (phách 3) rút còn **`0,25` phách** thay vì `1,0`, để nhả trước pattern kế. Hai nốt đầu vẫn `1,0`.

Điều kiện: `_juglar_region_last(ctx, bar, patterns)` — **chỉ ô cuối vùng Juglar**, không phải mọi ô `mode == "thin"`. Một ô thin ở giữa vùng vẫn để nốt cuối ngân `1,0` vì pattern còn tiếp; chỉ ô cuối vùng mới cần nhả sớm.

**Precedence với ô đệm (mục 2)**: khi ô cuối vùng Juglar **đồng thời là ô transition** (B→A, bar 69 trên ACB 1M II), **ô đệm thắng ở pipeline đầy đủ**. Ô đệm bỏ mọi attack trong phách cuối, nên nốt lead phách 3 biến mất; rule 1.3 không còn gì để rút trên chính ô đó. Test nghiệm thu của 1.3 chỉ chạy trên ô cuối vùng **không phải transition bar**; với bar 69, test nghiệm thu thuộc mục 2 (có gap rõ, không có attack mới ở phách cuối). Unit test gọi trực tiếp `_render_torroba_bar` vẫn thấy `0,25` vì cushion chạy sau đó.

### 1.4. Test cần thêm/cập nhật

- Bass có mặt ở **cả 3 phách** với hợp âm không có dây buông trong hệ written (F major ở Si♭).
- Bass mỗi phách dài `1,0`.
- Chùm thường: nốt thứ 4 dài `0,5`; chùm cuối ô: `0,25`.
- Ô cuối vùng **không phải transition bar**: nốt lead cuối dài `0,25`.
- Cập nhật `test_juglar_bar_before_the_return_stays_a_chunk`:
  - Test này gọi **trực tiếp** `_render_torroba_bar`, chưa qua cushion, nên `last` vẫn đổi từ `1.0` xuống `0.25` cho nốt cuối (bar 69). Ở pipeline đầy đủ, cushion mới là bước xóa nốt phách 3.
  - `:3814` đang assert **cả 9 nốt bar 68** dài `0,25`; đổi thành **per-cluster**: hai chùm đầu có nốt thứ 4 dài `0,5`, chùm cuối ô dài `0,25`.
- Thêm test đo **sau pipeline đầy đủ** (không chỉ `_render_torroba_bar`) để chắc bass không bị `_repair` / `_resolve` / `_rewrite_bass` xóa, và bar 69 có cushion thay vì nốt phách 3.
- Đã implement bước **hạ voicing bè cao một quãng tám** (mục 1.1 bước 2): `_juglar_bass()` sửa trực tiếp các nốt voice 1 của chùm trong `lead` rồi thử lại `(2, 1)`. Trên ACB 1M II nhánh này không chạy.
- **Đã tìm ra thủ phạm thật của cú bass `0,5`**: `guitar_scale_passages._drop_region()` cắt mọi bè còn ngân khi một scale passage bắt đầu giữa phách (bar 47/49 có passage mở ở móc cuối phách 2). `_rewrite_bass()` giờ truyền `hold_bass_until` cho Torroba, để bass ngân tới cú bass kế tiếp mà `_rewrite_bass` sẽ đặt, thay vì cắt đôi phách.

---

## 2. Ô đệm A–B–A

### 2.1. Luật

- Dùng **ô cuối cùng của vùng đi trước**, không thêm ô.
- Áp ở **cả A→B và B→A**.
- Nội dung ô bị **thưa đi**: giữ bass/chord đệm, bỏ bớt lead, để **một phách trống rõ** ở cuối ô.
- Không cắt ngang nốt đang ngân. Nốt trước khoảng trống được viết kết thúc đúng **mốc phách**, không cắt giữa móc.

### 2.2. Hình dạng ô đệm

Gọi `beat` là số móc của **một phách** trong meter hiện tại:

```python
beat = 3 if ctx.kind == "6/8" else 2   # 6/8: dotted quarter; 3/4 và 4/4: quarter
gap = (bar + 1) * ctx.epb - beat
```

- 3/4: `epb=6`, `beat=2`, `gap` = móc 4 → trống phách 3.
- 4/4: `epb=8`, `beat=2`, `gap` = móc 6 → trống phách 4.
- 6/8: `epb=6`, `beat=3`, `gap` = móc 3 → trống **nửa sau ô** (một phách dotted-quarter). Không dùng `end - 2` cho 6/8 vì như vậy chỉ chừa 2/6 ô, không thành một phách.
- `ctx.kind == "other"`: bỏ qua cushion, giữ nguyên hành vi cũ (Torroba hiện chỉ dùng 3/4, 4/4, 6/8).

Quy tắc:

- Giữ nguyên attack trước `gap`.
- Bỏ mọi **attack mới** trong `[gap, end)` ở lead, support và low.
- Nốt **lead/support** bắt đầu trước `gap` mà ngân qua `gap` thì cắt đúng `gap` (note-off ở mốc phách, không phải giữa tiếng).
- **Bass** không bị cắt: nếu một cú bass phát trước `gap` đã dài qua `gap` thì để ngân tự nhiên; nhưng không thêm cú bass mới trong `[gap, end)`, nên phách trống vẫn là rest thật ở bè cao. Trên ACB 1M II, cú bass cuối ở bar 46/69 bắt đầu đúng `gap` (hoặc trước đó) nên bị bỏ/để ngân, khoảng trống `2,0–3,0` sạch ở bè cao.
- Không còn `_silence` đúng móc cuối.

Kết quả trên ACB 1M II (đo lại sau khi vào code):

| Ô | Trước | Sau |
|---|---|---|
| 46 (A→B) | lead chạy tới `2,75`, bass 3 phách | lead tới `1,5`, bass phách 1 ngân hết `3,0` (được phép ngân qua gap); **trống `2,0–3,0` ở lead** |
| 69 (B→A) | lead `0 / 1 / 2`, bass `1,5` | lead `0 / 1`, bass figure `1,5`; **trống `2,0–3,0` ở lead** |

### 2.3. Cách làm

Thêm helper trong `guitar_patterns.py`:

```python
def _torroba_cushion(ctx, bar, lead, support, low):
    """Ô cuối vùng đi trước thành ô đệm: thưa attack, giữ bass, chừa một phách trống."""
```

Gọi helper ở **cả hai đường**:

1. `_smooth_boundaries()` — đường framed, đường app đang chạy cho 1M/1W/1Y.
2. `_transitions()` — đường unframed.

Trong mỗi đường, trước vòng xử lý hiện tại:

- Chỉ áp khi `ctx.ensemble == "torroba"`, cả `bar` và `bar + 1` đều là **body** (`ctx.kind_at.get(..., "phrase") not in _PEDAL`), và `_bar_pattern(ctx, bar, patterns) != _bar_pattern(ctx, bar + 1, patterns)`. Không đặt ô đệm ở mối nối intro→body hoặc body→outro.
- **Đọc seam từ hai bar liền kề**, không đọc `section.end - 1`: phrase có thể trải qua vạch section (ACB 1M II: phrase Castillo trải tới bar 46 trong khi section B bắt đầu ở bar 46), nên `_bar_pattern(bar) != _bar_pattern(bar + 1)` mới là ô cuối vùng thật. `_torroba_cushion_bars()` quét `range(ctx.bars - 1)`; `_smooth_boundaries()` hợp danh sách đó với `_boundary_bars()`.
- Trong `_transitions()`, `bar = (ctx.phrases[left].end - 1) // ctx.epb`.
- Gọi `_torroba_cushion()` rồi `continue`, bỏ qua nhánh `_silence` / `_relax_texture` / `_plant_pickup` cho bar đó.
- `apply_sonatina_downbeats()` bỏ pickup khi bar trước là ô đệm, nếu không grace `2,75` sẽ lấp lại gap.

**Guard `owned`**: không bỏ guard cho ensemble khác. Với Torroba, **cố ý cho phép cushion chạy trên figure bar**, vì hai mối nối A–B–A trên ACB 1M II đều là figure bar (bar 46 là Castillo cadence, bar 69 là `JUGLAR_THIN`). Cushion chỉ bỏ attack **sau `gap`**, nên phần đầu của figure vẫn còn; đây là thưa có chủ đích, không phải xé cả figure. Test phải khẳng định phần đầu figure còn và phách cuối trống.

**Vì sao không đặt sau guard `owned`**: nếu đặt sau, bar 46/69 bị bỏ qua và không có ô đệm — đúng lỗi hiện tại. Vì vậy nhánh Torroba phải đứng **trước** guard `owned`, và tự chịu trách nhiệm giữ phần đầu figure.

### 2.4. Test cần thêm/cập nhật

- A→B và B→A đều có ô đệm, ở **cả đường framed và unframed**.
- Ô đệm có ít nhất một phách không có attack mới.
- Không có nốt nào bị cắt trước khi hết duration ghi (kiểm tra note-off trùng mốc phách).
- Bass của ô đệm vẫn còn ít nhất một cú.
- Note bị cắt ở gap không để lại tie treo: `tie_start` bị clear trên segment bị cắt, và `tie_stop` ở bar kế tiếp (nếu tie vượt vạch nhịp) cũng bị clear.
- Phần đầu figure bar (trước `gap`) vẫn còn ít nhất một attack lead.
- 6/8: gap là 3 móc, không phải 2.

---

## 3. Động lực Castillos A đầu

> **Phạm vi**: đợt này chỉ sửa **phrase Castillo A đầu**. `_Pen._local_lead()` là nguyên nhân chung của mọi figure render qua `_Pen` (`castillo`, `sonatina`, `fandanguillo`, `danza`, và phần figure của `torroba_tremolo` / `alcaniz` / `olite`), nhưng kế hoạch **không đổi `_local_lead`** và **không mở rộng contour** sang các pattern khác. Muốn sửa đồng loạt phải làm thêm một đợt riêng (xem ghi chú cuối mục 3.4).

### 3.1. Luật

- A đầu có đường cong rõ: **mở nhẹ → căng dần → nhả**.
- Nốt lặp cùng cao độ **không cùng velocity**; chênh tối thiểu **4** đơn vị.
- Chỉ đổi velocity/contour, không đổi cao độ hay articulation của figure.
- Contour phải sống qua `apply_guitar_wave()`.
- Khi một cặp nốt lặp đã chạm sàn `44`, **nâng nốt trước** để giữ chênh lệch, không hạ nốt sau xuống dưới sàn.

### 3.2. Cách làm

Thêm helper trong `guitar_torroba.py`:

```python
def apply_castillo_first_a_contour(ctx, lead, patterns):
    """Contour velocity cho vùng Castillos A đầu, sau arch và trước sóng."""
```

Xác định **A đầu**: phrase body **đầu tiên** của movement. Nếu pattern của nó không phải `castillo` (ví dụ chương 4/4 rally mở bằng `olite`), pass không làm gì — không contour vùng B contrast. Nếu đúng là `castillo`, vùng A gồm phrase đó **và mọi phrase body liền kề cũng `castillo`**, dừng ở pattern khác đầu tiên. Đây là cả vùng A (bar 10–46 trên ACB 1M II), không phải một phrase; A cuối sau B không nằm trong vùng nên giữ nguyên.

Với từng ô trong vùng:

1. Tính `progress = (onset - region.start) / max(1, region.end - region.start)` trên **cả vùng**.
2. `arc = round(5 * sin(pi * progress)) - 2` → khoảng `-2 … +3`, mở nhẹ, giữa căng, cuối nhả.
3. `beat_index = min(3, int(event.beat + 1e-9))` (phách 0, 1, 2, 3 của ô), rồi `beat_step = -2 * min(beat_index, 2)` → phách 1 `0`, phách 2 `-2`, phách 3 và 4 `-4`. Đây là **phách chứa onset** (floor), không phải thứ tự attack, nên bar 45 có 5 attack vẫn dùng đúng phách; nốt lệch phách như `0,5` vẫn thuộc phách 0.
4. Chỉ áp khi ô **phẳng** (`max - min < 4`) hoặc có **nốt lặp liền kề**. Ô đã có contour tự nhiên (ví dụ ô 10) được giữ nguyên.
5. `velocity = clamp(velocity + arc + beat_step, 44, 72)`.
6. Sau đó quét nốt lặp liền kề: nếu cùng `midi` và chênh velocity `< 4`, **hạ nốt sau xuống `earlier - 4`** nếu `earlier - 4 ≥ 44`; nếu không, **nâng nốt trước lên `later + 4`** (clamp `72`) để khoảng cách vẫn ≥ 4. Điều kiện phải kiểm tra chính giá trị được ghi (`earlier - 4`), không phải `later - 4`; nếu kiểm sai, cặp `45/48` sẽ ghi `41` và rơi dưới sàn.

Gọi trong `guitar_patterns.py`:

```python
lead = apply_torroba_sung_arch(ctx, lead, patterns)
lead = apply_castillo_first_a_contour(ctx, lead, patterns)
low = apply_juglar_thumb(ctx, lead, low, patterns)
```

Thứ tự này quan trọng: contour chạy **sau** arch (arch không ghi đè) và **trước** sóng (sóng dịch đều nên giữ chênh lệch).

### 3.3. Kết quả mong đợi

Bảng dưới ghi **delta contour** (giá trị cộng vào velocity viết, trước sóng), không ghi velocity tuyệt đối — vì velocity nghe được còn phụ thuộc center của sóng từng ô:

Đo lại sau khi vào code (velocity viết, trước sóng) trên các ô phẳng của vùng A:

| Ô | Trước | Sau |
|---|---|---|
| 11 | `72 / 72 / 72` | `70 / 69 / 67` |
| 12 | `74 / 72 / 73 / 72 / 72` | `72 / 71 / 70 / 69 / 67` |
| 15 | `72 / 72 / 72` | `72 / 70 / 68` |
| 28 | `72 / 72 / 72 / 72` | `72 / 68 / 72 / 71` |
| 45 | `75 / 72 / 73 / 72 / 73` | `72 / 71 / 70 / 68 / 67` |

Cộng thêm `arc` của cả vùng (khoảng `-2 … +3`) để tạo đường cong mở → căng → nhả giữa các ô. Điều kiện test là **spread toàn vùng ≥ 8**, **hai nốt lặp liền kề lệch ≥ 4** (bước 6 bảo đảm), và **spread sau sóng ≥ 4**. Không giá trị nào được dưới sàn `44`; nếu contour muốn xuống thấp hơn, nâng nốt trước thay vì hạ nốt sau. Bar 45 dùng đúng phách chứa onset nên 5 attack vẫn đọc `0 / -2 / -4 / -4 / -4`, chỉ khác arc và clamp `72` so với bảng cũ.

Sàn `44` là **velocity viết**, không phải velocity nghe. Sóng dịch mỗi ô một center: `nghe = round(center) + (viết − 64)`. Trên ACB 1M II vùng A, center khoảng `49–52`, nên viết `44` nghe khoảng `29–32` — sát sàn nghe của body (`SPEECH = 22`, `PEDAL_FLOOR = 20`). Đo 8 movement có contour (4 mã × `1W`/`1M`): velocity viết nhỏ nhất là `47` (PVS 1M I), ACB 1M II là `51`, nên sàn `44` hiện chưa bao giờ chạm. Hạ sàn viết sẽ hạ luôn độ nghe được; muốn release sâu hơn thật thì hạ đồng thời sàn viết và `beat_step` rồi nghe lại.

### 3.4. Test cần thêm

- A đầu: mọi ô có nốt lặp liền kề đều có chênh velocity ≥ 4.
- A đầu: spread velocity trong **cả vùng** ≥ 8 (test dùng hai phrase castillo liền nhau).
- Gọi `apply_guitar_wave()` sau contour, xác nhận spread vẫn ≥ 4.
- A cuối (phrase castillo sau B) không bị đổi.
- Cặp lặp sát sàn (`earlier = 45`, `later = 48`) không đẩy nốt nào xuống dưới `44`.
- Ô đã có contour tự nhiên (spread ≥ 4, không nốt lặp liền kề) được giữ nguyên.

**Nếu muốn fix đồng loạt các pattern khác** (đợt riêng, không nằm trong kế hoạch này):

- **Cách A (khuyến nghị)**: tổng quát hoá helper thành `apply_torroba_contour(ctx, lead, patterns, *, only_pattern=...)`, chạy sau `apply_torroba_sung_arch` và trước sóng, rồi bật cho từng pattern với đường cong riêng. An toàn vì nằm ngoài `_Pen`, nhưng cần test nghe cho từng pattern.
- **Cách B (rủi ro hơn)**: sửa `_local_lead()` để giữ contour do figure viết (ví dụ thêm cờ `contour` trên attack, hoặc giữ delta so với mức trung bình bar). Cách này chạm mọi figure `_Pen` cùng lúc, dễ đổi nhịp điệu velocity của sonatina/fandanguillo/danza, nên phải đo lại toàn bộ Torroba.

---

## 4. Tempo 92–132

### 4.1. Bảng mới

`TORROBA_TEMPO_MIN = 92`, `TORROBA_TEMPO_MAX = 132`.

Bảng dưới là **sàn** (`TORROBA_TEMPO_FLOOR`), không phải BPM cuối: BPM cuối = `min(132, max(body.bpm, sàn))`, nên chương đã nhanh hơn sàn vẫn giữ nguyên.

| Mood | Nhịp | Sàn hiện tại | Sàn mới |
|---|---|---:|---:|
| calm | 3/4 | 96 | **92** |
| calm | 4/4 | 96 | **92** |
| calm | 6/8 | 104 | **96** |
| selloff | 3/4 | 104 | **96** |
| selloff | 4/4 | 104 | **96** |
| selloff | 6/8 | 116 | **108** |
| rally | 3/4 | 112 | **104** |
| rally | 4/4 | 120 | **112** |
| rally | 6/8 | 120 | **112** |
| volatile | 3/4 | 124 | **116** |
| volatile | 4/4 | 132 | **124** |
| volatile | 6/8 | 140 | **132** |

Đúng ví dụ `140 → 132`. Trung bình hạ khoảng `8` BPM.

### 4.2. Hành vi

`retarget_torroba_tempo()` vẫn **chỉ nâng tới sàn, không hạ chương đã nhanh hơn sàn**, và cắt ở trần mới `132`. Vì vậy:

- ACB 1M II (3/4 calm, `96`) **giữ nguyên 96**, vì `96 > 92`.
- Chương 6/8 volatile `140` bị `min(132, max(140, 132))` → **132**.
- Chương 4/4 volatile `96` → **124**.
- Chương 3/4 rally `96` → **104**.

### 4.3. Việc kèm theo

- Cập nhật docstring `retarget_torroba_tempo()`: `92–132`.
- Sửa comment trong `guitar_torroba.py:52-53`: `"nothing is lowered unless it passed 140"` → `"nothing is lowered unless it passed 132"`.
- Cập nhật `docs/sonify-guitar-torroba-tempo-plan.md` (tiêu đề, mục 1, bảng constants, dòng `96–140`, `140 → 132`), `docs/sonify-guitar-torroba-aba-tempo.md`, `docs/sonify-guitar-torroba-castillos-frames.md`.
- Cập nhật thêm `docs/sonify-guitar-torroba-plan.md`: dòng khoảng **25** (`96–124 / 96–132 / 108–140`) và dòng khoảng **232** (`4/4, 96–132 BPM`), vì đây là hai chỗ vẫn ghi dải cũ.
- Tăng `SPAN_REVISION` trong `backend/app/sonify/audio.py` từ `"70"` lên `"71"` vì audio đổi.
- Cập nhật test `test_torroba_tempo_floor_lifts_only_and_reads_the_new_meter`:
  - rally 4/4: `120 → 112`
  - volatile 4/4: `132 → 124`
  - selloff 3/4: `104 → 96`
  - mood `None`, 4/4: `96 → 92`
  - nhịp lạ: `96 → 92`
- Cập nhật các kỳ vọng `112 / 132 / 104` trong `test_span.py` theo bảng mới.
- **Không đổi** kỳ vọng `test_torroba_month_frames_after_the_meter_change` (`:397`, `torroba[0].spec.bpm == 96`): 3/4 calm giữ `96` vì `96 > 92`. Ghi chú để không sửa nhầm.

### 4.4. Bảng ảnh hưởng lên test_span.py

| Test / dòng | Kỳ vọng cũ | Kỳ vọng mới |
|---|---:|---:|
| `test_torroba_tempo_floor_lifts_only...` rally 4/4 | 120 | **112** |
| cùng test, volatile 4/4 | 132 | **124** |
| cùng test, selloff 3/4 | 104 | **96** |
| cùng test, mood `None` 4/4 | 96 | **92** |
| cùng test, nhịp lạ | 96 | **92** |
| `test_torroba_month_frames...` `torroba[1].spec.bpm` | 112 | **104** |
| cùng test, `torroba[3].spec.bpm` | 120 | **112** |
| `test_torroba_quarter...` `quarter[0].spec.bpm` | 104 | **96** |
| cùng test, `quarter[1].spec.bpm` | 112 | **104** |
| cùng test, `quarter[2].spec.bpm` | 132 | **124** |
| `test_torroba_quarter...` `year[1].spec.bpm` | 112 | **104** |
| cùng test, `year[2].spec.bpm` | 120 | **112** |

Các dòng `96 / 100 / 104 / 120` còn lại chỉ đổi nếu body thực tế cao hơn sàn mới; chạy test để chốt, không sửa máy móc.

---

## 5. Thứ tự thực hiện

1. **Tempo**: sửa constants + comment `132` + `span.py` docstring + tests `test_span.py`; chạy test tempo trước để khóa dải mới.
2. **Juglar bass + duration**: sửa `_render_juglar_bar()`, thêm `_juglar_bass()`; chạy test Juglar.
3. **Ô đệm**: thêm `_torroba_cushion()` và gọi ở **cả** `_smooth_boundaries()` (framed) lẫn `_transitions()` (unframed); test cả hai đường. Vì ô đệm thắng rule 1.3 trên bar 69, test của bước 2 phải tránh bar 69 hoặc chờ bước 3 rồi cập nhật.
4. **Động lực A đầu**: thêm `apply_castillo_first_a_contour()`, gọi sau `apply_torroba_sung_arch()`; chạy test dynamics.
5. Tăng `SPAN_REVISION` lên `"71"`.
6. Chạy lại toàn bộ:
   - `backend/tests/test_sonify_guitar_torroba.py`
   - `backend/tests/test_span.py`
   - `backend/tests/test_guitar_wave.py`
7. Đo lại bằng các script trong `backend/tmp/`:
   - `diag_user_summary.py` — bass đủ phách, nốt cuối, velocity A đầu.
   - `diag_user_prewave.py` — contour trước sóng.
   - `diag_juglar_bass_all.py` — không còn phách nào thiếu bass.
   - `diag_user_framed.py` — bar 46/69 trên **đường framed** thật của app.
   - `diag_frame_path.py` — xác nhận app đi qua `_smooth_boundaries`, không phải `_transitions`.

---

## 6. Tiêu chí nghiệm thu

- [x] ACB 1M II: ô 58, 59, 64 có bass ở cả 3 phách, mỗi cú `1,0` — đo **sau pipeline đầy đủ**.
- [x] ACB 1M II: không ô Juglar nào có bass ngắn hơn `1,0` (trừ lưới an toàn bất khả kháng, không xảy ra trên bản này).
- [x] Chùm thường: nốt thứ 4 dài `0,5`; chùm cuối ô: `0,25`.
- [x] Ô cuối vùng Juglar **không phải transition bar**: nốt lead cuối dài `0,25`.
- [x] Bar 69 (vừa là cuối vùng Juglar vừa là transition B→A): **ô đệm thắng**; không còn attack lead ở phách 3, có gap `2,0–3,0`.
- [x] A→B (bar 46) và B→A (bar 69): ô cuối vùng đi trước có ≥ 1 phách không attack mới, không có note-off giữa móc; áp ở **cả framed và unframed**.
- [x] Phần đầu figure bar (trước `gap`) vẫn còn ít nhất một attack lead.
- [x] A đầu Castillos (cả vùng A, không chỉ phrase đầu): spread velocity ≥ 8; nốt lặp liền kề lệch ≥ 4; spread còn ≥ 4 sau sóng; không giá trị **viết** nào dưới `44` (sàn nghe thấp hơn sau sóng).
- [x] Mọi `spec.bpm` Torroba nằm trong `[92, 132]`; `140 → 132`.
- [x] `SPAN_REVISION = "71"`.

---

## 7. Đối chiếu feedback review

Đã kiểm tra từng điểm và cập nhật kế hoạch:

| Điểm review | Kết luận | Đã sửa |
|---|---|---|
| 0.1: F có dây buông A=45 nên nguyên nhân gốc khác | **Một phần sai**: trong hệ written của Si♭, dây buông là `42/47/52`; F không có dây buông. `_torroba_bass=45` bị `_sounding_bass` loại vì `45-2=43` không phải dây buông. Nguyên nhân gốc vẫn là **tầng lọc dây buông**; diag đã in rõ. | Cập nhật 0.1 với số đo thật |
| 3.3: bar 28 có `42` dưới sàn `44` | Đúng | Sửa thành `44`; thêm luật nâng nốt trước khi chạm sàn |
| 3.2: `beat_index` chưa định nghĩa | Đúng | Định nghĩa `floor(event.beat)`, clamp 0–3 |
| 3.1: luật lặp ≥ 4 mâu thuẫn sàn 44 | Đúng | Thêm nhánh nâng nốt trước thay vì hạ nốt sau |
| 2.2: `end - 2` sai cho 6/8 | Đúng | `beat = 3` cho 6/8, `gap = end - beat` |
| 2.3: bỏ guard `owned` sẽ xé figure | **Một phần đúng**: bar 48/69 đều là figure bar, nên nếu đặt sau guard thì không có ô đệm. Kế hoạch cho Torroba chạy **trước** guard nhưng chỉ bỏ attack sau `gap`, giữ đầu figure; test khẳng định đầu figure còn. | Cập nhật 2.3 và test |
| 1.3 ↔ 2: bar 69 xung đột | Đúng | Ghi rõ **ô đệm thắng**; test 1.3 tránh transition bar |
| 1.4: test bar 68 assert cả 9 nốt 0,25 | Đúng | Đổi thành per-cluster |
| 1.1: fallback cuối bỏ playability | Đúng | Thêm bước hạ voicing, đo sau pipeline, ghi rõ lưới an toàn |
| 4.3: comment `140` và doc `sonify-guitar-torroba-plan.md` | Đúng | Thêm vào danh sách sửa |
| 4.3: test month `:397` giữ 96 | Đúng | Ghi chú không sửa nhầm |
| **Mới**: app dùng framed → `_smooth_boundaries`, không phải `_transitions` | **Đúng, quan trọng** | Thêm 0.2, 2.3, 5, 6: cushion phải gọi ở cả hai đường |
| **Tự kiểm tra**: ví dụ 3.3 (`54/50/46`) không khớp công thức `-2`/phách, và `spread ≥ 4` mâu thuẫn `≥ 8` | Đúng | Đổi bảng sang **delta contour** (`0/-2/-4`), đồng bộ mọi chỗ thành `spread toàn phrase ≥ 8` |
| **Tự kiểm tra**: 2.2 vừa bảo bỏ attack `low` trong gap vừa bảo bass ngân qua gap | Đúng | Tách luật: lead/support cắt tại `gap`; bass không cắt nhưng không thêm attack mới trong gap |

---

## 8. Đợt sau: tổng quát hoá contour (Cách A)

> **Trạng thái**: đã chốt hướng, **chưa implement trong đợt này**.

Mục tiêu: các pattern Torroba khác cũng có thể nhận contour động lực mà không bị `_Pen._local_lead()` ghi đè. Đợt này **không** sửa `_local_lead`; contour vẫn nằm ngoài `_Pen`, sau `apply_torroba_sung_arch` và trước `apply_guitar_wave`.

### 8.1. API

Trong `guitar_torroba.py`:

```python
def apply_torroba_contour(
    ctx,
    lead,
    patterns,
    *,
    only_pattern: str | None = None,
):
    """Contour velocity cho pattern Torroba, chạy sau arch và trước sóng."""
```

- `only_pattern=None`: áp cho mọi pattern Torroba trong `_TORROBA_PATTERNS`.
- `only_pattern="castillo"`: giữ đúng hành vi đợt này (A đầu Castillos).
- Hàm dùng chung phần tính `arc`, `beat_step`, clamp `44…72`, và bước xử lý nốt lặp ≥ 4.
- Đợt này có thể refactor `apply_castillo_first_a_contour()` thành wrapper gọi `apply_torroba_contour(..., only_pattern="castillo")`, hoặc giữ nguyên rồi mở rộng sau.

### 8.2. Đường cong theo pattern

Mỗi pattern cần một đường cong riêng, không dùng chung một `arc`:

| Pattern | Hướng contour |
|---|---|
| `castillo` | A đầu: mở nhẹ → căng → nhả (đợt này). A cuối giữ nguyên. |
| `sonatina` | Đỉnh theo `phrase.apex`, không nhất thiết giữa phrase. |
| `fandanguillo` | Giữ sàn 68 ở phách mạnh, contour chỉ trên các phách yếu. |
| `danza` | Giữ sàn 68 ở phách mạnh, tránh làm phẳng bước nhảy strong-beat. |
| `torroba_tremolo` | Contour trên nốt đầu mỗi phách; các ngón sau giữ offset hiện có. |
| `alcaniz` | Full: contour theo phrase; thin/opening: giữ nguyên. |
| `olite` | Full: contour theo phrase; thin: giữ nguyên. |

### 8.3. Test

- Mỗi pattern: spread velocity toàn phrase ≥ 8 (trừ pattern giữ sàn 68, đo phần trên sàn).
- Nốt lặp liền kề lệch ≥ 4, kể cả khi chạm sàn `44` (nâng nốt trước).
- Contour sống qua `apply_guitar_wave()`: spread sau sóng ≥ 4.
- `castillo` A cuối **không đổi**.
- Không pattern nào bị `_local_lead()` kéo về một mức phẳng sau khi contour chạy.

### 8.4. Rủi ro

- Cách A an toàn hơn Cách B vì không chạm `_Pen`, nhưng vẫn có thể đổi cảm giác dynamics của sonatina/fandanguillo/danza. Phải nghe và đo từng pattern trước khi bật mặc định.
- Nếu một pattern đã có contour tự nhiên, chỉ áp khi ô phẳng hoặc có nốt lặp, giống điều kiện của Castillos A đầu.
