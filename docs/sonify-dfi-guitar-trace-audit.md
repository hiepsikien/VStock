# DFI guitar trace audit — pattern nào làm chỉ số đo sai?

> **Trạng thái:** audit trên `main` `d0385c0` (2026-11-03), DFI v4. PR này là **docs + diagnostic probe**; renderer/DFI code chưa sửa.
>
> **Quy ước:** `mN` là index **0-based**, nên `m1` = movement II. Các bảng dùng `m1`, `m2`, `m3` theo quy ước này.
>
> **Câu hỏi:** ngoài `thumb_cantabile` của Villa/Barrios, còn pattern guitar nào làm trace bỏ mất nốt giá và khiến DFI thấp/null?
>
> **Kết luận ngắn:** có **3 pattern lỗi thật** — `thumb_cantabile`, `etude1`, `torroba_tremolo` (Juglar). Một số texture Torroba trông giống lỗi nhưng **đang đúng**: `castillo`/`sonatina`/`danza`/`alcaniz`/`olite` hạ lead xuống bè trung, nhưng trace cũng hạ theo và `_TRACE_PRICE_LINE` giữ giá gốc. Barrios `tremolo` và Bach prelude cũng đúng vì nốt giá chính vẫn rơi đúng lưới eighth. Ngoài việc **thiếu** point, generic trace còn **thừa** point khi nốt đệm trùng pitch.

---

## 1. TL;DR

| Pattern | Ensemble | Vấn đề | Mức độ | Trạng thái |
|---|---|---|---|---|
| `thumb_cantabile` | Villa, Barrios | Line bị dịch −12/−24 và snap vào bass; trace exact-pitch bỏ nốt | **Nặng**, phụ thuộc thứ tự section | Lỗi trace |
| `etude1` | Villa | Nốt giá chỉ nằm ở beat 1.75 / 2.25 (off eighth-grid) | **Rất nặng** | Lỗi trace |
| `torroba_tremolo` (Juglar) | Torroba | Giá nằm ở ngón 1/2/3 sau beat (+0.25/+0.5/+0.75); chỉ ngón +0.5 rơi lưới | **Nặng khi Juglar chiếm phần lớn movement** | Lỗi trace |
| `castillo`, `sonatina`, `danza`, `alcaniz`, `olite` | Torroba | Lead bị hạ một quãng 5 diatonic xuống bè trung | Không | **Đúng** — trace hạ theo |
| `sonatina` (4/4, 3/4) | Torroba | Chỉ offset 1/5 không attack ở lead; quarter 0/4 ngân phủ | Không | **Đúng** — coverage đọc duration |
| `tremolo` | Barrios | 4 sixteenth lặp mỗi quarter; 3 nốt off-grid | Không | **Đúng** — quarter đầu on-grid |
| `bach_prelude` | Bach | Giá ở móc kép chẵn, bậc phụ ở móc kép lẻ | Không | **Đúng** — chẵn rơi lưới eighth |
| frame (warmup/intro/outro/cooldown) | — | Point vẫn sinh; `_grid` mới loại | ⚠️ | Nên truyền `frame_bars` sớm |
| `villa_pattern`, `chord_melody`, `study`, `preludio`, `andante`, `elegiaque`, `cantabile`, `noviembre`, `brouwer_etude`, `elogio_pizz`, `sarabande`, `galop`, `mozart_var`, `vals`, `hemiola`, `polca`, `choro`, các Bach còn lại | — | Line nằm ở lead, viết trên lưới eighth | Không | **Đúng** |

---

## 2. Trace guitar đang hoạt động thế nào?

`render_guitar_score()` gọi:

```python
price_trace = trace_from_notes(
    [*lead, *support, *low],
    line=line,                 # _TRACE_LINE, thường là ctx.melody
    prices=trace_prices,
    epb=meter.eighths_per_bar,
    bar_beats=meter.quarter_beats,
    voice="price",
)
```

Sau đó `pitch` được remap về `_TRACE_PRICE_LINE` (line trước khi Torroba hạ quãng), còn `sounding_pitch` giữ MIDI thật.

Guitar **không** truyền `snap_to_line=True` (khác symphony/ambient ở các nhánh khác): nó ghi MIDI **đã viết** rồi mới remap về line gốc. Đó là lý do trace guitar đo “nốt đã viết”, không đo “ý định”. `trace_from_notes()` đã có `carrier` từ v4, nhưng guitar chưa dùng; `NoteEvent` lại frozen và không có cờ “nốt này mang giá”, nên carrier một mình không đủ để phân biệt line với bè đệm.

`render_guitar_score()` cũng **không** truyền `frame_bars` vào `trace_from_notes()`. Frame bar vẫn sinh trace point; `dfi._grid()` mới loại chúng sau. Vì vậy audit phải tách `frame pts`; nên truyền `frame_bars` ngay từ trace.

Có hai bộ lọc quyết định một nốt có thành trace point hay không:

1. **Phải đúng cao độ** (`backend/app/sonify/dfi.py`, `trace_from_notes`):
   - Mặc định `octave_tolerant=False`.
   - Nốt phải có `note.midi == line[eighth]` chính xác.
2. **Phải đúng lưới eighth** (`_event_eighth`, dòng ~137):
   ```python
   grid = event.beat * 2.0
   if abs(grid - round(grid)) > 0.01:
       return None   # móc kép lẻ, sixteenth lẻ, +0.25/+0.75... đều bị bỏ
   ```

Vì vậy trace chỉ đúng khi **writer đặt nốt giá đúng pitch của line và đúng lưới eighth**. Pattern nào cố ý đổi register, đổi voice, hoặc đặt nốt giá lệch lưới đều có thể bị mất.

Docs đã cảnh báo đúng chỗ này:

> nếu writer đổi bè mà helper không đọc, coverage vẫn có thể conservative — **sửa gốc vẫn là ghi trace tại writer**.
> — `docs/sonify-data-fidelity-index.md` §9.1

---

## 3. Ba pattern lỗi thật

### 3.1. `thumb_cantabile` — Villa và Barrios

**Code:**

- `backend/app/sonify/guitar_villa.py` `_place_thumb()` (~dòng 194)
  - thử `shift in (-12, -24)`; chọn `min((overflow, abs(shift)))`, tức ưu tiên ít tràn register rồi mới −12 trước −24
  - sau đó `_compress_monotone()` / `quantize_strong_beats()` / clamp vào `[floor, top]`
- `_render_thumb()` (~dòng 259) ghi line đã dịch vào **low**
- `trace_from_notes()` nhận `low`, nhưng so với `line` gốc → **không khớp**

Ví dụ VNINDEX / 1M / Villa / movement II — viết là **m1**, index 0-based; meter thật là **6/8**, bpm 72 (`Prelude — Chord Melody — Prelude`):

| Chỉ số | Giá trị |
|---|---:|
| Source bars | 1135 |
| Musical bars | 108 |
| Trace points | **108** |
| Bars có trace | **40 / 108** |
| Coverage | **0.338** |
| Shape | 0.360 |
| Motion | 0.187 |
| DFI | **13.2** |

Trace **đầy đủ** chỉ ở section `Chord Melody` ở giữa (bar 46–69). Hai section `Prelude` ở đầu/cuối dùng low thumb bị dịch octave nên gần như không có trace point; ngoài ra generic trace còn sinh point rác ở vài bar thumb/frame (xem §3.1.1).

Đổi thứ tự section (m2 — movement III, 6/8, bpm 120, `Chord Melody — Prelude — Chord Melody`) thì Chord Melody chiếm hai đầu:

| Movement | Title | Trace | Coverage | DFI |
|---|---|---:|---:|---:|
| m1 (II) | Prelude — Chord Melody — Prelude | 108 | 0.338 | **13.2** |
| m2 (III) | Chord Melody — Prelude — Chord Melody | 277 | 0.720 | **49.5** |

Đây đúng là hiện tượng bạn thấy: **cùng hai điệu, đổi thứ tự thì điểm khác hẳn**.

Barrios cũng dùng `thumb_cantabile`, nhưng thường chỉ một section nên lỗi nhẹ hơn:

| Bài | Coverage | DFI |
|---|---:|---:|
| VNINDEX 1M Barrios m1 | 0.682 | 45.6 |
| VNINDEX 1M Barrios m2 | 0.772 | 42.2 |

**Nếu trace đúng** (thử ghi trace tại writer cho từng nốt low của thumb):

| Movement | Hiện tại | Trace đúng |
|---|---:|---:|
| VNINDEX 1M Villa m1 | 13.2 / coverage .338 | **58.2 / .899** |
| VNINDEX 1M Villa m2 | 49.5 / coverage .720 | **62.2 / .885** |

Chỉ bật `octave_tolerant=True` không đủ: với `max_octaves=3`, movement II chỉ lên **35.1** (với `max_octaves=1` là 34.5), vì `_place_thumb` còn snap/compress line vào chord/register, không phải lúc nào cũng đúng octave.

#### 3.1.1. Trace dương tính giả trong section thumb

Đây không chỉ là **thiếu** point. Generic trace còn tạo **point rác** khi nốt đệm/hợp âm tình cờ trùng `line[eighth]`.

`--per-pattern` cho VNINDEX 1M Villa m1:

| Pattern | Bars | Trace points | Bars có trace | Frame points |
|---|---:|---:|---:|---:|
| `chord_melody` | 24 | 74 | 24 | 0 |
| `thumb_cantabile` | 68 | **32** | **14** | 0 |
| `pedal` (frame) | 16 | 2 | 2 | **2** |

40 bar có trace = 24 bar Chord Melody + **14 bar thumb** (12, 13, 17, 26–27, 39–43, 86–87, 95–96) + **2 bar frame** (102–103). Trong 32 point ở thumb: **23 point từ lead đệm**, **9 point từ low**; đây là các nốt đệm trùng pitch chứ không phải line thumb. (Review đếm 22 point theo một filter hẹp hơn; kết luận không đổi: toàn bộ span thumb cần bị suppress khỏi generic trace.)

Vì vậy “merge generic trace + dedupe theo `(bar, beat)`” **không đủ**: dedupe chỉ bỏ point trùng chỗ, không xoá point rác ở beat khác. Cần **suppress generic trace trong writer-owned span**, giống cách `yield_spans` xử lý symphony/jazz.

---

### 3.2. `etude1` — Villa

**Code:**

- `backend/app/sonify/guitar_villa.py` `_render_etude1_bar()` (~dòng 422)
- Hai nốt giá trong lead:

```python
high_at = {
    7: (sung_beat2, min(start + 2, last), 0.5),
    9: (sung_beat3, min(start + 4, last), 1.75),
}
```

- `index 7` → beat `7/4 = 1.75`
- `index 9` → beat `9/4 = 2.25`

Cả hai đều **không** rơi lưới eighth:

```text
beat 1.75 × 2 = 3.5  → _event_eighth trả None
beat 2.25 × 2 = 4.5  → _event_eighth trả None
```

Low bass ở beat 0 là bass đệm, không phải line. Vì vậy gần như **toàn bộ nốt giá của Étude 1 bị bỏ**.

Bằng chứng thật:

| Bài | Movement | Trace | Coverage | DFI |
|---|---|---:|---:|---:|
| VNINDEX 3M Villa | m0 — `Etude 1` | **20** | **0.019** | **0.9** |
| HPG 1M Villa | m3 — `Etude 1` | **12** | — | **null** |

`--per-pattern` cho HPG m3: `etude1` có **84 bar, 1.314 note, 5 trace point, 3 bar có trace, 703 note off-grid**; phần còn lại là `pedal` frame (7 point, 7 frame). Đây là lý do 12 point không đủ để `compute()` có 2 component.

`HPG 1M Villa m3` hiện `DFI —` **không phải vì `n_moves` thấp**: đo được `n_moves = 321`, `confidence` cũng không phải cổng chặn. Nguyên nhân là trace chỉ có 12 point (7 point rơi vào frame bar, 5 point ở body), nên `_shape`, `_motion`, `_resolution`, `_structure` đều trả `None`, chỉ còn `volume = 0.3945`. `compute()` thấy `len(components) == 1 < 2` và trả `None` tại `backend/app/sonify/dfi.py` (~dòng 1054). Đây là gate **quá ít component**, không phải gate `n_moves`.

`dfi_probe.py` cũng crash trên chính movement này trước khi sửa: `motion=None` nhưng format `:.3f`. Probe đã được sửa dùng `fmt(row["base"].motion)`, nên lệnh `HPG 1M guitar villa` giờ chạy được và in `—` cho Motion.

Thử bổ sung trace tại writer (mỗi nốt `high_at` ghi đúng beat + đúng `hairpin_eighth`):

| Bài | Hiện tại | Trace đúng (ước lượng) |
|---|---:|---:|
| VNINDEX 3M Villa m0 | 0.9 / coverage .019 | **26.3 / coverage .631** |
| HPG 1M Villa m3 | null / 12 trace | **26.1 / coverage .577** |

Con số 26 chưa phải đích cuối: bản mô phỏng chỉ thêm point sau khi score đã compose, nên Motion vẫn có thể sai. Fix thật phải ghi trace ngay trong `_render_etude1_bar()`.

**Lưu ý cho P0:** `backend/app/sonify/guitar.py` (~dòng 190) remap `pitch` bằng:

```python
eighth = point.bar * epb + int(round(point.beat * 2))
```

Với `beat=1.75`, `round(3.5) = 4` (banker's rounding), nên nếu point vẫn chỉ mang `beat` thì remap lấy `intended[start+4]` trong khi giá đúng là `[start+2]`. Point writer-owned phải mang **origin eighth** (field mới, ví dụ `price_eighth`) hoặc remap phải dùng origin đó, không suy lại từ beat off-grid. Nếu không, P0 sẽ thêm point nhưng `pitch`/`price` vẫn lệch nhau.

---

### 3.3. `torroba_tremolo` / Juglar — Torroba

Đây là texture bạn nhớ. Nhưng điểm thấp **không phải vì line nằm ở bass**. Trong Juglar:

- **thumb** (low/bass) đánh root ở beat, là accompaniment;
- **ba ngón** (lead) đánh nốt giá, nhưng bắt đầu **sau beat**:

`backend/app/sonify/guitar_torroba.py` `_render_juglar_bar()` (~dòng 3846):

```python
for index, offset in enumerate(JUGLAR_FINGERS):
    lead.append(
        _heard(
            bar,
            beat + (index + 1) * JUGLAR_STEP,  # +0.25, +0.5, +0.75
            midi,
            ...
        )
    )
```

Chỉ nhánh **3/4 full chunk** mới bị. 4/4 và 6/8 đi qua `_downbeat_only()`; bar `quarter_notes` (thin hoặc bar cuối region) viết lead ở beat 0/1/2, đều on-grid.

`JUGLAR_STEP = 0.25`. Với mỗi beat:

| Ngón | Beat | `beat × 2` | Lưới eighth? |
|---|---:|---:|---|
| 1 | +0.25 | 0.5 | ❌ |
| 2 | +0.50 | 1.0 | ✅ |
| 3 | +0.75 | 1.5 | ❌ |

Vì vậy trace chỉ bắt được **ngón thứ hai**, và map nó vào **eighth kế tiếp** (`line[beat+1]`), không phải eighth của beat (`line[beat]`). Khi giá đổi trong beat, trace ghi sai giá; khi giá đứng, may mắn khớp.

Bằng chứng thật:

| Bài | Title | Juglar bars | Trace Juglar | Trace/bar | Danza trace/bar | DFI | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| PVS 1M | Juglar — Danza — Juglar | 68 | 145 | **2.13** | 4.00 | **17.9** | **0.311** |
| REE 1M | Juglar — Danza — Juglar | 67 | 153 | **2.28** | 4.08 | **24.3** | **0.503** |
| VNINDEX 1M m0 | Castillo — Juglar — Castillo | 7 | 18 | 2.57 | — | 55.8 | 0.942 |

Khi Juglar chỉ 7 bar (VNINDEX m0), lỗi bị pha loãng nên DFI vẫn 55.8. Khi Juglar chiếm 2/3 movement (PVS/REE), DFI rơi còn 17.9/24.3.

`--per-pattern` VNINDEX 1M Torroba m0: `torroba_tremolo` 7 bar / 76 note / **18 trace point** / **36 note off-grid** / 56 note near-line; `castillo` 81 bar / 253 point. Con số 18 point cho 7 bar (2.57/bar) thấp hơn 3 giá/bar, và các point nằm ở beat 0.5/1.5/2.5 chứ không phải beat 0/1/2.

Thử ghi trace tại writer cho từng beat Juglar:

| Bài | Hiện tại | Trace đúng (ước lượng) |
|---|---:|---:|
| PVS 1M m1 | 17.9 / .311 | **40.4 / .791** |
| REE 1M m1 | 24.3 / .503 | **38.7 / .955** |

Lưu ý: bản mô phỏng làm Motion thấp đi vì point được thêm sau score. Fix thật phải ghi point ngay trong `_render_juglar_bar()` với `pitch` là line tại **beat origin**, không phải tại ngón +0.5.

---

## 4. Những texture trông giống lỗi nhưng đang đúng

### 4.1. Torroba hạ lead xuống bè trung — `castillo`, `sonatina`, `danza`, `alcaniz`, `olite`

`backend/app/sonify/guitar_patterns.py` `_lower_torroba_stretches()` (~dòng 1772) hạ một số stretch xuống **một quãng 5 diatonic**:

```python
for shift in ...:
    ctx.melody[eighth] = lowered
```

Nhưng trace cũng được lấy từ `ctx.melody` **sau khi hạ**, rồi `_TRACE_PRICE_LINE` giữ line gốc để remap `pitch`. Vì vậy:

- nốt thật = line đã hạ
- trace so với line đã hạ → khớp
- DFI đọc `pitch` đã remap về giá gốc

Kiểm tra thực tế trên VNINDEX 1M Torroba (`--per-pattern`):

| Movement | Pattern | Note khớp | Trace points | Kết luận |
|---|---|---|---:|---:|---|
| m0 | `castillo` | 254 | 253 | 1 note trùng attack bị dedupe |
| m1 | `danza` | 104 | 104 | Khớp |
| m2 | `alcaniz` | 61 | 61 | Khớp |
| m3 | `olite` | 316 | 316 | Khớp |

`Note khớp` đếm **note** (có thể trùng attack hoặc nằm trong frame); `Trace points` dedupe theo `(bar, beat)`. Vì vậy `254` note khớp / `253` point không phải mất nốt — chỉ là hai voice cùng đánh một attack. Cột `frame pts` trong `--per-pattern` tách riêng point ở frame.

**Không sửa** phần này. Đây là register choice, không phải mất trace.

### 4.2. `sonatina` giữ nốt giá weak eighth bằng quarter

Trong `_render_sonatina_moving()`:

- lead đánh quarter ở offset **0** (và **4**);
- lead còn đánh slurred eighth ở offset **2, 3** (và **6, 7**);
- chỉ offset **1 và 5** không có attack ở lead — đó là chỗ quarter đang ngân. Support có thể đánh inner note ở 1/5, nhưng đó là bè đệm, không phải nốt giá.

Trace point ở beat mạnh có `duration_beats` phủ offset 1/5, nên coverage vẫn tính. Shape/Motion chỉ thấy ít attack hơn — đó là đặc điểm texture, không phải trace bỏ nốt. Không thêm point giả.

### 4.3. Barrios `tremolo`

`_tremolo()` tạo 4 sixteenth mỗi quarter:

```text
beat + 0, +0.25, +0.5, +0.75
```

Ba nốt sau off-grid, nhưng **nốt repeat 0 nằm đúng beat** và mang đúng melody pitch của quarter. Trace bắt được nốt này. VNINDEX 1M Barrios m3 (`--per-pattern`):

| Pattern | Bars | Trace points | Exact notes | Off-grid | Ghi chú |
|---|---:|---:|---:|---:|---|
| `tremolo` | 59 | 380 | 380 | 464 | 6.44 point/bar; off-grid chỉ là lặp cùng pitch |

Không có lỗi cấu trúc. Nếu sau này `_tremolo` đổi để mỗi sixteenth mang một pitch khác thì mới thành lỗi.

### 4.4. Bach prelude và các móc kép

`_render_bach_prelude_bar()` đặt giá ở **móc kép chẵn**:

```python
lead.extend(_spell16(slot, 1, price, ...))        # slot = eighth * 2 → chẵn
lead.extend(_spell16(slot + 1, 1, neighbor, ...)) # lẻ → bậc phụ
```

Móc kép chẵn có `beat × 2` nguyên → qua `_event_eighth`; móc kép lẻ bị bỏ có chủ ý. `--per-pattern` VNINDEX 1M Bach m0: `bach_prelude` 36 bar / 288 trace point / 288 note khớp / 288 off-grid (ornament), tức đúng 8 point/bar.

Các Bach còn lại (`bach_fuga`, `bach_bourree`, `bach_gavotte`, `bach_sarabande`, `bach_allemande`) dùng `_sustain(ctx.melody, ...)` ở lead, nằm trên lưới eighth. `bach_gigue`/`bach_courante`/`bach_chaconne` có scale/approach trang trí nhưng nốt giá chính vẫn ở lead/eighth; audit không thấy mất cấu trúc. Riêng `bach_gigue` clamp `sung` vào `_bach_lead_high()` và step cho pickup, nên nếu sau này mở register rất rộng cần test lại — hiện tại chưa thấy mất nốt giá trong corpus đã đo.

### 4.5. Các pattern lead `_sustain` khác

Các pattern sau viết line ở lead, trên lưới eighth, nên trace ổn:

- Sor: `study`, `galop`, `mozart_var`, `cantabile`, `elegiaque`
- Villa: `villa_pattern`, `chord_melody`, `etude11`
- Barrios: `preludio`, `andante`, `chord_melody`, `vals`, `hemiola`, `polca`, `choro`
- Brouwer: `noviembre`, `brouwer_etude`, `elogio_pizz`, `sarabande`
- Torroba: `castillo`, `sonatina`, `fandanguillo`, `danza`, `alcaniz`, `olite` (trừ phần bass/held đã giải thích)
- `pedal` / frame: **không phải trace bị loại ngay**. `render_guitar_score()` gọi `trace_from_notes()` **không** truyền `frame_bars`, nên frame bar vẫn sinh point; `dfi._grid()` mới loại chúng sau. Vì vậy `--per-pattern` in cột `frame pts`, và audit phải trừ frame khỏi “trace/bar”. Nên truyền `frame_bars` ngay từ trace để tránh point rác.

### 4.6. Bảng đầy đủ theo ensemble

| Ensemble | Pattern | Trạng thái | Ghi chú |
|---|---|---|---|
| Sor | `study`, `galop`, `mozart_var`, `cantabile`, `elegiaque` | ✅ | Lead `_sustain` / on-grid |
| Villa | `villa_pattern`, `chord_melody`, `etude11` | ✅ | Lead on-grid |
| Villa | `thumb_cantabile` | ❌ | Bass −12/−24 |
| Villa | `etude1` | ❌ | Lead beat 1.75 / 2.25 |
| Barrios | `preludio`, `andante`, `chord_melody`, `vals`, `hemiola`, `polca`, `choro`, `tremolo` | ✅ | Lead/quarter on-grid |
| Barrios | `thumb_cantabile` | ❌ | Cùng lỗi Villa |
| Brouwer | `noviembre`, `brouwer_etude`, `elogio_pizz`, `sarabande` | ✅ | Lead on-grid |
| Bach | `bach_prelude` | ✅ | Giá ở móc kép chẵn |
| Bach | `bach_fuga`, `bach_bourree`, `bach_gavotte`, `bach_sarabande`, `bach_allemande` | ✅ | Lead `_sustain` |
| Bach | `bach_gigue`, `bach_courante`, `bach_chaconne` | ✅* | Có clamp/step ở cực register; test lại nếu mở rộng |
| Torroba | `castillo`, `sonatina`, `fandanguillo`, `danza`, `alcaniz`, `olite` | ✅ | Lowered lead được trace theo |
| Torroba | `torroba_tremolo` | ❌ | Chỉ 3/4 full chunk; 4/4/6/8 và quarter_notes an toàn |
| Chung | `pedal` | ✅ | Lead `_sustain` |
| Chung | frame (warmup/intro/outro/cooldown) | ⚠️ | Point vẫn sinh; `_grid` mới loại. Nên truyền `frame_bars` sớm |

---

## 5. Nguyên nhân gốc chung

1. **Trace được dựng từ nốt đã viết, không phải từ ý định của writer.**
   Writer biết chính xác nốt nào mang giá; helper chỉ suy lại bằng `midi == line[eighth]`.

2. **Không có khái niệm “register/voice đã đổi”.**
   `thumb_cantabile` dịch −12/−24; Torroba hạ quãng 5; `etude1`/Juglar đặt nốt lệch lưới. Helper chỉ có exact match và một cờ `octave_tolerant` không đủ.

3. **Lưới phân tích là eighth, trong khi vài texture viết giá trên sixteenth.**
   `_event_eighth()` bỏ mọi nốt `beat × 2` không nguyên. Đúng cho ornament, sai khi nốt giá **chỉ** nằm ở sixteenth.

4. **Trace hiện tại vừa thiếu vừa thừa.**
   Thiếu point thật ở `thumb_cantabile`/`etude1`/Juglar; thừa point rác khi nốt đệm trùng pitch. Vì vậy thiết kế đúng là **writer-owned span/ownership** (“nốt này mang giá”), không phải nới tolerance.

5. **DFI không có guard “trace bất thường”.**
   Khi trace rơi còn 12–20 point, DFI vẫn trả 0.9 hoặc `null` thay vì cảnh báo “trace incomplete”. Người dùng thấy như bản nhạc mất fidelity.

---

## 6. Fix đề xuất

### P0 — writer-side trace cho 3 pattern lỗi

Không sửa bằng cách nới `octave_tolerant` toàn cục. Ghi trace ngay tại writer:

| Pattern | Nơi ghi | `pitch` | `sounding_pitch` | `beat` |
|---|---|---|---|---|
| `thumb_cantabile` | `_render_thumb()` | `ctx.melody[eighth]` (giá gốc) | MIDI low thật | beat thật của nốt low |
| `etude1` | `_render_etude1_bar()` | `ctx.melody[hairpin_eighth]` | MIDI lead thật | `1.75` / `2.25` |
| `torroba_tremolo` | `_render_juglar_bar()` | `ctx.melody[origin]` | MIDI ngón đầu | beat origin (hoặc first finger +0.25) |

Mỗi point cần thêm **origin eighth** để remap không suy lại từ beat off-grid:

```python
PriceTracePoint(
    bar=bar,
    beat=beat,
    price_eighth=origin_eighth,   # field mới, hoặc field tương đương
    duration_beats=duration,
    price=prices[origin_eighth],
    pitch=float(intended_pitch),
    sounding_pitch=float(written_midi),
    role="attack",
    voice="price",
)
```

Lý do: `guitar.py` (~dòng 190) đang remap bằng `int(round(point.beat * 2))`; với `beat=1.75` thì `round(3.5)=4`, lấy sai `intended[start+4]` thay vì `[start+2]`.

Sau đó **suppress generic trace trong writer-owned span** (giống `yield_spans`), rồi merge point writer. Dedupe theo `(bar, beat)` chỉ xử lý trùng chỗ, **không xoá** point rác ở beat khác.

### P1 — tái dùng `carrier` + kênh writer→trace

`carrier` **đã có sẵn** trong `trace_from_notes()` (`dfi.py:162`, dùng ở `fill_trace_from_notes` dòng 278). Vấn đề là `NoteEvent` frozen, không có cờ “nốt này mang giá”, nên `carrier(note, eighth)` một mình không phân biệt line với bè đệm.

P1 nên là:

- thêm kênh writer→trace (contextvar/span) để writer nói **nốt nào** mang giá;
- dùng `carrier` cho các span đó;
- suppress generic trace trong cùng span;
- không bật `octave_tolerant=True` toàn cục: nó chỉ cứu một phần `thumb_cantabile` và có thể nhận nhầm hợp âm.

### P2 — guard/UI dựa trên hạ tầng sẵn có

- Gate `len(components) < 2` trong `compute()`: trả trạng thái **“chưa đo được”**, không hiển thị 0.9/null như điểm fidelity.
- Hạ `DfiBreakdown.confidence` khi `len(trace_points) / len(price_eighths)` thấp; không thêm field `trace_confidence` mới.
- Thêm `pattern`/`trace_version` vào `DfiBreakdown` (không phải sidecar mới) để debug.
- Ca mạnh: HPG 1M Villa m0 có `score 58.6`, `motion=None`, `coverage 1.000`, `confidence=high` — UI vẫn báo điểm cao dù Motion không đo được.

### Tests cần thêm

1. `thumb_cantabile` — VNINDEX 1M Villa m1: trace ≥ 250, coverage ≥ .8, DFI không rơi dưới 40.
2. `etude1` — VNINDEX 3M Villa m0: trace > 0, coverage ≥ .6, DFI không null.
3. Juglar — PVS 1M Torroba m1: chỉ assert trên tập bar do `torroba_tremolo` render, `trace/bar ≥ 2.8` trong tập đó, coverage ≥ .7. Không assert trace/bar toàn movement vì tỉ lệ section đổi.
4. Barrios `thumb_cantabile` — VNINDEX 1M Barrios m1/m2: coverage không giảm khi đổi thứ tự section.
5. Regression: `castillo`, `danza`, `tremolo` (Barrios), `bach_prelude` giữ trace/exact như cũ.
6. Thêm test **dương tính giả**: trong span `thumb_cantabile`, generic trace không được sinh point từ lead/low; `--per-pattern` chỉ còn point writer.
7. Thêm test **frame**: `render_guitar_score()` truyền `frame_bars`; `frame pts = 0` trong `--per-pattern`, hoặc `_grid` vẫn loại đúng.
8. Assert theo **range/order**, không assert số DFI tuyệt đối.

---

## 7. Phụ lục — cách đo

Các số trong tài liệu lấy từ `main` `d0385c0`, dữ liệu `as_of 2026-11-03`. Quy ước: **`mN` là index 0-based**, nên `m1` = movement II.

```bash
cd backend
.venv/bin/python scripts/dfi_probe.py VNINDEX 1M guitar villa
.venv/bin/python scripts/dfi_probe.py VNINDEX 3M guitar villa
.venv/bin/python scripts/dfi_probe.py PVS 1M guitar torroba
.venv/bin/python scripts/dfi_probe.py REE 1M guitar torroba
.venv/bin/python scripts/dfi_probe.py HPG 1M guitar villa --per-pattern
.venv/bin/python scripts/dfi_probe.py VNINDEX 1M guitar villa --per-pattern
.venv/bin/python scripts/dfi_probe.py VNINDEX 1M guitar torroba --per-pattern
```

`--per-pattern` in bảng trace theo pattern, gồm `frame pts` và `exact notes`; đây là cách tái lập các số `253/254`, `104/104`, `61/61`, `316/316`.

Bảng chi tiết theo movement:

| Bài | Ensemble | Movement | Pattern chính | DFI | Coverage | Trace |
|---|---|---|---:|---:|---:|---:|
| VNINDEX 1M | Villa | m0 | Chord Melody | 57.3 | 1.000 | 253 |
| VNINDEX 1M | Villa | m1 | Prelude — Chord Melody — Prelude | 13.2 | .338 | 108 |
| VNINDEX 1M | Villa | m2 | Chord Melody — Prelude — Chord Melody | 49.5 | .720 | 277 |
| VNINDEX 3M | Villa | m0 | Etude 1 | **0.9** | **.019** | 20 |
| HPG 1M | Villa | m0 | Chord Melody | **58.6** | **1.000** | 232 |
| HPG 1M | Villa | m1 | Prelude — Chord Melody — Prelude | 7.6 | .258 | 104 |
| HPG 1M | Villa | m2 | Prelude — Chord Melody — Prelude | 23.4 | .341 | 119 |
| HPG 1M | Villa | m3 | Etude 1 | **null** | — | 12 |
| PVS 1M | Torroba | m1 | Juglar — Danza — Juglar | 17.9 | .311 | 242 |
| REE 1M | Torroba | m1 | Juglar — Danza — Juglar | 24.3 | .503 | 263 |
| VNINDEX 1M | Torroba | m0 | Castillo — Juglar — Castillo | 55.8 | .942 | 276 |
| VNINDEX 1M | Barrios | m1 | — (có thumb) | 45.6 | .682 | 232 |
| VNINDEX 1M | Barrios | m2 | — (có thumb) | 42.2 | .772 | 224 |

HPG m0 là ca P2 mạnh: `score 58.6`, `motion=None`, `coverage 1.000`, `confidence=high` — DFI vẫn báo điểm cao dù Motion không đo được. Đây là lý do P2 phải gate `len(components) < 2` và hạ confidence theo trace coverage, không chỉ dựa vào `n_moves`.

PR này là **docs + diagnostic probe**; renderer/DFI code chưa sửa.

---

## 8. Kết luận

- **`thumb_cantabile`**, **`etude1`**, **`torroba_tremolo`/Juglar** là ba lỗi trace thật, không phải DFI thấp đúng.
- **Torroba hạ lead xuống bè trung** (`castillo`/`sonatina`/`danza`/`alcaniz`/`olite`) **không lỗi**; trace đã hạ theo line và remap về giá gốc.
- **Torroba Juglar** không phải “melody ở bass”; thumb là accompaniment, line nằm ở ba ngón lead nhưng lệch lưới.
- Mức ảnh hưởng phụ thuộc **tỷ lệ và thứ tự section**: cùng pattern, đổi thứ tự có thể đổi DFI từ 13 lên 50 (Villa) hoặc 18 lên 40+ (Juglar).
- Trace hiện tại **vừa thiếu vừa thừa**: thiếu point thật ở ba pattern lỗi; thừa point rác khi nốt đệm trùng pitch. Fix đúng là **writer-owned span/ownership**, không chỉ dedupe hay tolerance.
- `--per-pattern` trong `dfi_probe.py` tái lập được các bảng; probe đã sửa crash `motion=None`. Renderer/DFI code vẫn chưa sửa trong PR này.
