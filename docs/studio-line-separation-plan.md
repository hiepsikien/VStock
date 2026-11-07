# Kế hoạch: sửa register/role rồi tách bè Price / MA5 / MA20

Trạng thái: **Phase 0 đã implement; Phase 1 chờ nghe thử Phase 0**.
Phạm vi: `release/studio-v2.1`, chỉ Render Piece / luồng Studio pattern mới.  
Đối tượng áp dụng: ensemble `villa` (Villa-Lobos) và các piece tạo từ `StudioPiece`; **không** áp dụng cho legacy render.

Tài liệu liên quan:

- `docs/studio-render-piece-plan.md` — Render Piece, plan/tag/series.
- `docs/studio-schottish-pattern-plan.md` — pattern production.
- `backend/app/studio/render_piece.py` — rebind pitch hiện tại.
- `backend/app/studio/texture_resolve.py` — resolve `PitchRef`.
- `backend/app/sonify/studio_piece.py` — arrangement / authored cell.

---

## 0. Phasing

### Phase 0 — sửa lỗi register/role (đã implement, chờ nghe thử)

Mục tiêu duy nhất: bass không còn bị đẩy cao, và role bass/mid/lead đúng
theo pitch order.

Phạm vi Phase 0:

1. Phân vai theo **từng source voice line**, dùng median pitch của cả line:
   ```text
   voice 1 (lead)              -> lead
   non-lead median thấp nhất   -> bass
   non-lead median còn lại     -> mid, thấp → cao
   ```
   Không phân vai lại tại từng onset, vì một nốt mới thấp hơn có thể “cướp”
   bass đang ngân và làm `_resolve` cắt nốt bass.
2. Rewrite `voice` **một lần cho cả source line** về role voice duy nhất:
   ```text
   lead = 1, mid = 2/4, bass = 3
   ```
   Vì mỗi source voice là một line monophonic, mapping 1-1 này vẫn giữ
   validator monophonic và không tạo overlap.
3. Bass-only figure (chỉ có một non-lead voice) vẫn là bass; không tự nâng
   thành lead.
3. Bass dùng register thật:
   - bắt đầu từ `Chord.bass_midi` (C2–B2);
   - fold lên octave cho đến khi `>= guitar_floor` (40), giữ nguyên pitch class.
4. Mid dùng chord tone được fold vào band mid runtime:
   ```text
   mid_low=50 .. mid_high=65
   ```
5. Lead vẫn là `melody_eighth` / price melody; không đổi.
6. Chỉ áp dụng cho `StudioPiece` + `villa`; legacy render giữ nguyên.
7. Bump `STUDIO_RENDER_REVISION` khi note thực tế đổi.

Phase 0 **không** đổi sang MA5/MA20. Nếu Phase 0 nghe ổn, mới làm Phase 1.

### Phase 1 — tách line Price / MA5 / MA20 (deferred)

Sau khi nghe Phase 0:

- lead = price;
- mid = MA5;
- bass = MA20;
- cùng role-by-pitch và register như Phase 0;
- soft ordering + warning.

Toàn bộ mục 1–11 dưới đây mô tả Phase 1; các mục có ghi “Phase 0” là bắt
buộc trước khi Phase 1.

---

## 1. Vấn đề hiện tại

Render Piece đang rebind literal MIDI như sau:

```text
voice 1 / lead  -> melody_eighth   (price melody)
voice 2 / mid   -> chord_degree(2)
voice 3-4 / bass -> chord_root
```

Hệ quả:

1. Lead bị `_place_melody` ép vào register treble của guitar
   (`treble_floor=59 .. treble_top=81`), nên có đoạn bị đẩy lên cao.
2. Mid **không có contour riêng**; nó chỉ là chord tone degree 2. Khi harmony
   đổi, mid có thể nhảy hoặc bám quá sát lead.
3. Bass chỉ là chord root, không có đường nền riêng.
4. Không có cơ chế giữ trung bình `bass < mid < lead`; voice-order hiện tại
   chỉ được kiểm tra ở mức từng note và còn bị relax cho preview.

### 1.1. Bằng chứng từ file render thực tế

File `6461171b...musicxml` (32 bar, 2/4):

| Voice | Sounding MIDI | Written MIDI | Mean | Vai trò hiện tại |
|---|---:|---:|---:|---|
| voice 1 | 59–79 | 71–91 | 67.9 | Lead |
| voice 2 | 52–74 | 64–86 | 62.5 | Đang bị coi là Mid |
| voice 3 | 57–69 | 69–81 | 61.3 | Đang bị coi là Bass |
| voice 4 | 59–76 | 71–88 | 66.2 | Mid |

- Nốt thấp nhất: **sounding E3 = 52**, written E4.
- Guitar low E: **sounding E2 = 40**, written E3.
- Bass hiện tại cao hơn khả năng thấp nhất của guitar đúng **1 octave**.
- Voice 2 mới là bè thấp nhất thật sự, nhưng bị map vào mid; voice 3 bị map
  vào bass. Hai bè bị đảo vai trò.

### 1.2. Nguyên nhân kỹ thuật

1. `_resolve_chord` dùng `chord.pitches[d-1]`, mà các chord constant nằm quanh
   C4. Vì vậy `chord_root` trả về khoảng 57–67 (A3–G4), không phải bass.
   `Chord.bass_midi` (36–47) đã có nhưng chưa được dùng trong Render Piece.
2. `render_texture_bar` phân loại theo **voice number**:
   ```text
   voice 1 -> lead
   voice 2/4 -> support
   voice 3 -> low
   ```
   Trong khi UI `buildRoleLanes` phân loại non-lead theo **pitch order**.
   Hai bên không khớp.
3. `_bind_production_pitches` cũng dùng voice number, nên voice 2 (bass thật)
   nhận `chord_degree(2)` thay vì root.
4. Guitar MusicXML ghi cao hơn sounding 1 octave (`written = sounding + 12`),
   nên bass E3 hiện lên thành E4 trên khuông — đúng như ảnh chụp.

Mục tiêu của thay đổi này là tách **ba đường độc lập** nhưng vẫn nằm trong
harmony của bar, sau khi đã sửa register/role ở Phase 0.

---

## 2. Quyết định thiết kế

### 2.0. Phase 0 — role và register

Trước khi có line, phải sửa hai thứ:

```text
role = pitch order, không phải source voice number
bass = chord.bass_midi, fold lên >= guitar_floor (40)
mid  = chord tone fold vào 50..65
```

Role chuẩn sau khi bind:

```text
lead = voice 1
mid  = voice 2/4
bass = voice 3
```

Nếu không làm Phase 0, MA5/MA20 vẫn bị đặt sai octave và vẫn nghe cao.

### 2.1. Ba nguồn đường

```text
Lead = price
Mid  = MA5
Bass = MA20
```

- Lead giữ nguyên `melody_eighth` / price melody.
- Mid dùng MA5 của close series.
- Bass dùng MA20 của close series.
- Tất cả note cuối cùng đều được quantize về chord tone của bar.
- Bar cadence / close (`VILLA_CADENCE`) **không** áp dụng line; giữ nguyên rule
  cadence hiện có.

### 2.2. MA tính trên series gốc, trước khi vào form

MA phải tính trên close series **trước khi resample/chia form**, không tính
trên các bar đã được nhạc hoá.

```text
source closes
  -> MA5 / MA20
  -> slice đúng form.bars
  -> map vào register band
  -> snap chord tone
  -> render
```

Không dùng lookahead: chỉ tính trên đoạn series sẽ render (`form.bars` đầu
tiên), không lấy MA từ các bar nằm ngoài form.

Với bar đầu chưa đủ window, dùng trung bình của các giá trị đã có
(`min(index + 1, window)`), không chèn zero.

### 2.3. Window cấu hình được

Mặc định:

```json
{
  "mid": { "source": "ma", "window": 5 },
  "bass": { "source": "ma", "window": 20 }
}
```

Không hardcode `5/20` trong renderer. Cho phép đổi window để A/B:

- `5/10`: nhanh, nhưng mid/bass dễ trùng contour.
- `5/20`: mặc định đề xuất.
- `8/21`, `10/30`: dùng khi series dài hơn.

Với dữ liệu thật `1M` chỉ có ~21 daily closes, `MA20` gần như toàn series;
khi đó cần cho phép window ngắn hơn (`3/8` hoặc `5/10`). Đây là lý do window
phải là config, không phải hằng số âm nhạc.

### 2.4. Ordering mềm

Không áp đặt từng note:

```text
mid < lead tại mọi onset   # không làm
```

Chỉ cần trung bình:

```text
mean(bass) < mean(mid) < mean(lead)
```

cho các note không thuộc cadence/close.

Nếu lệch:

1. thử dịch cả line một octave trong guitar range;
2. nếu vẫn lệch, giữ render và trả warning;
3. **không** reject toàn bộ piece.

---

## 3. Vì sao chọn MA5 / MA20

Đo trên chính 3 demo series hiện tại (`1D`, `1W`, `1M`):

| Series | MA50 đổi hướng | MA50 mean \|Δ\| | MA5/MA10 correlation |
|---|---:|---:|---:|
| 1D · 64 bar | 2 | ~0.39 | 0.62 |
| 1D · 128 bar | 4 | ~0.32 | **0.90** |
| 1W · 128 bar | 6 | ~0.12 | 0.77 |
| 1M · 128 bar | 10 | ~0.44 | 0.40 |

Kết luận:

- **MA50 quá phẳng** với series ngắn; bass gần như đứng yên.
- **MA5/MA10 quá gần nhau**, nhất là 1D 128 bar; mid và bass mất vai trò riêng.
- **MA5/MA20** là điểm cân bằng: mid đủ nhanh, bass đủ chậm nhưng vẫn có contour.

Đây là lựa chọn mặc định, không phải bất biến. Khi có dữ liệu thật dài/ngắn
khác nhau, window sẽ được chọn theo `1D / 1W / 1M` hoặc theo số bar.

---

## 4. Kiến trúc đề xuất

### 4.0. Role assignment (Phase 0, bắt buộc)

Trước khi bind pitch, phân vai theo **từng source voice line**:

```text
voice 1                    -> lead
non-lead median thấp nhất  -> bass
non-lead median còn lại    -> mid, thấp → cao
```

Điều này bỏ phụ thuộc vào voice number gốc của MusicXML nhưng vẫn giữ được
duration: một line bass đang ngân không bị line khác lấy mất role khi có nốt
mới thấp hơn.

Sau đó rewrite `voice` một lần cho cả source line:

```text
lead = 1, mid = 2/4, bass = 3
```

Vì mapping là 1-1 giữa source line và role voice, spec vẫn monophonic.
Support được gán rõ voice 2/4 để `guitar.py` không collapse hai line về voice 2.

Với figure chỉ có một non-lead voice: giữ làm bass, không nâng thành lead.

### 4.1. Series và MA

Thêm bước tính line trong `backend/app/studio/render_piece.py`:

```text
resolved bars (close, volume)
  -> closes = [bar.close for bar in bars[:form.bars]]
  -> ma5[eighth]  = rolling_mean(closes, 5)
  -> ma20[eighth] = rolling_mean(closes, 20)
```

MA được tính theo **bar**, sau đó map sang eighth khi tạo line MIDI.
Có thể dùng cùng một giá trị cho toàn bộ eighth trong bar, hoặc resample theo
eighth nếu muốn contour mịn hơn. MVP: giữ một giá trị/bar để bass/mid ổn định.

### 4.2. Pitch reference mới

Thêm một runtime pitch kind:

```text
line_eighth
  line: "ma5" | "ma20"
  eighth: int
  offset?: int
```

- `eighth` là absolute eighth index trong piece, giống `melody_eighth`.
- `bind_texture` phải shift cả `line_eighth` khi figure được tile sang bar khác,
  không chỉ shift `melody_eighth`.
- Compressed 1-bar frame cũng phải cộng `pitch_eighth_offset` cho nửa sau, giống
  fix đã làm cho `melody_eighth`; nếu không, mid/bass nửa sau sẽ đọc line của
  nửa đầu.
- `line_eighth` là **runtime-only**: không xuất hiện trong source `TextureSpec`
  do user tạo, không được promote, không thay đổi schema publish hiện tại.

`PitchRef` cần thêm field `line` và constructor:

```python
PitchRef.line_eighth("ma5", eighth)
PitchRef.line_eighth("ma20", eighth)
```

Các field hợp lệ:

```text
line_eighth: ("line", "eighth", "offset")
```

### 4.3. Context line arrays

`StudioPiece` mang theo line MIDI arrays:

```python
@dataclass(frozen=True)
class StudioPiece:
    ...
    lines: Mapping[str, tuple[int, ...]] = field(default_factory=dict)
```

`render_patterned_voices` gắn lines vào `_Ctx`:

```python
ctx.line_pitches = dict(studio_piece.lines)  # nếu có
```

`texture_resolve.resolve_pitch` đọc:

```python
ctx.line_pitches["ma5"][eighth + offset]
ctx.line_pitches["ma20"][eighth + offset]
```

Nếu line thiếu hoặc eighth ngoài range: raise `TextureResolveError` rõ ràng,
không silent clamp.

### 4.4. Register band

Lấy đúng register runtime trong `backend/app/sonify/keys.py`:

```text
bass:  40..53   (E2..F3)
mid:   50..65   (D3..F4)
lead:  59..81   (B3..A5)
ceiling: 83
```

Band này chỉ là **target**, không phải hard validation. Guitar playability
(`_repair`, hand span, fret) vẫn là cổng cuối.

Phase 0 dùng band này cho bass/mid; Phase 1 dùng cùng band cho MA20/MA5.

### 4.5. Quantize vào harmony

Với mỗi line/bar:

1. normalize giá trị line về `[0, 1]` theo min/max của chính line đó;
2. map vào register band của voice;
3. chọn chord tone gần nhất trong band;
4. bass ưu tiên root/fifth; mid ưu tiên 3rd/5th/7th; lead ưu tiên chord tone
   hoặc scale tone gần nhất.

Không dùng `chord_degree(2)` / `chord_root` cố định nữa cho mid/bass trong
luồng mới.

Phase 0 dùng:

```text
bass target = Chord.bass_midi, fold lên >= 40
mid target  = chord tone gần nhất trong 50..65
```

Fold theo octave, **không clamp** — clamp sẽ đổi pitch class (C2 → E2).
Ví dụ:

```text
C2 36 -> C3 48
A2 45 -> A2 45
E2 40 -> E2 40
```

### 4.6. Soft ordering

Sau khi render (hoặc trước khi render nếu đã có đủ line arrays):

```text
lead_avg = mean(note.midi for voice 1, non-cadence)
mid_avg  = mean(note.midi for voice 2/4, non-cadence)
bass_avg = mean(note.midi for voice 3, non-cadence)
```

Nếu vi phạm:

- thử shift line `±12` trong range 40..83;
- ưu tiên giữ bass ổn định, dịch mid/lead trước;
- nếu vẫn vi phạm: warning `line order is soft: ...`, render vẫn thành công.

Warning phải nói rõ voice nào và average nào, ví dụ:

```text
line order is soft: mid 61.2 >= lead 60.8; kept the render
```

### 4.7. Playability context

`_playability_context` hiện dùng melody giả `[60] * 8192`. Với `line_eighth`:

- cấp thêm line arrays trung tính (cùng độ dài) để validator không crash;
- playability vẫn dùng range/voice/tab check như hiện tại;
- kết quả render thật là authority cuối cùng.

Không để việc thiếu line trong context làm hỏng validation offline.

---

## 5. Request / API

Thêm cấu hình line vào Render Piece request (optional, có default):

```json
{
  "lines": {
    "lead": { "source": "price" },
    "mid":  { "source": "ma", "window": 5 },
    "bass": { "source": "ma", "window": 20 }
  }
}
```

Default khi không gửi:

```json
{
  "lead": { "source": "price" },
  "mid":  { "source": "ma", "window": 5 },
  "bass": { "source": "ma", "window": 20 }
}
```

Chỉ chấp nhận:

```text
source: "price" | "ma"
window: integer 2..64
```

`window` phải nhỏ hơn hoặc bằng số bar sẽ render. Nếu lớn hơn, trả lỗi rõ
ràng, không tự truncate.

---

## 6. Phạm vi áp dụng

Chỉ khi:

```text
studio_piece is not None
ensemble == "villa"
variant == "guitar"
```

Không áp dụng cho:

- legacy `render()` không có `studio_piece`;
- source passage preview;
- các ensemble khác;
- production promote (source `TextureSpec` vẫn giữ literal MIDI và vẫn bị
  reject như hiện tại).

Render Piece vẫn là preview-only: không mutate `TEXTURE_CELLS`,
`SENTENCE_SPECS`, `STUDIO_DOORS`.

---

## 7. Cache / hash / revision

Phải đưa vào `renderHash`:

- `lines` config (`source`, `window`);
- line arrays đã resolve (nếu hash theo texture);
- `STUDIO_RENDER_REVISION`.

Phase 0 đổi note thực tế, nên bump ngay:

```python
STUDIO_RENDER_REVISION = 4
```

Phase 1 (line separation) bump thêm một lần nữa:

```python
STUDIO_RENDER_REVISION = 5
```

Lý do: cùng một request cũ có thể trả MusicXML/WAV khác sau khi thay đổi
role/register hoặc line policy. Không bump sẽ khiến cache cũ che mất thay đổi.

Ghi chú: revision đã lên **7** sau fix Studio pipeline scale fallback +
MusicXML voice cursor. Revision 6 là bản trung gian chưa release trong cùng
cụm fix; revision 5 là fix compressed seam.

---

## 8. Test plan

### 8.0. Phase 0

- Role by source-line median:
  - voice 1 luôn lead;
  - non-lead median thấp nhất thành bass dù voice gốc là 2;
  - non-lead median còn lại thành mid 2/4;
  - bass-only figure vẫn là bass, không bị nâng thành lead.
- Duration safety:
  - bass đang ngân không bị nốt mới thấp hơn cắt;
  - support source voice không collapse hết về voice 2.
- Compressed seam:
  - tie/slur không treo ở `cut`.
- Bass register:
  - `Chord.bass_midi` C2 36 → C3 48;
  - A2 45 giữ nguyên;
  - mọi bass nằm trong 40..53.
- Mid register:
  - chord tone được fold vào 50..65;
  - không clamp làm đổi pitch class.
- Render file thực tế:
  - nốt thấp nhất <= 53;
  - mean(bass) < mean(mid) < mean(lead);
  - bass không còn nằm trên mid.
- Legacy: render không có `studio_piece` giữ nguyên output.
- Compressed frame và voice 4 vẫn đúng sau khi đổi role.

### 8.1. Phase 1 unit

- `MA5` / `MA20` trên series ngắn, warmup đúng, không zero-pad.
- `line_eighth` shift theo `bind_texture` khi tile sang bar khác.
- `resolve_pitch`:
  - line đúng;
  - eighth ngoài range raise;
  - line thiếu raise.
- Quantize: mọi note non-cadence thuộc chord của bar.
- Register band:
  - bass trong 40..53;
  - mid trong 50..65;
  - lead trong 59..81;
  - không vượt guitar ceiling.

### 8.2. Phase 1 integration

- Render một piece `villa` với 3 line:
  - `mean(bass) < mean(mid) < mean(lead)` trên phần lớn bar;
  - nếu vi phạm thì có warning, không reject.
- Cadence/close không bị line ghi đè.
- So sánh legacy: render không có `studio_piece` phải giữ nguyên output.
- `1D/1W/1M` demo đều render được; `1M` đủ bar.

### 8.3. Regression

- `test_studio_render_api.py` cũ: cập nhật warning/rebind expectations.
- `test_studio_musicxml_api.py`: không đổi hành vi import.
- Full backend suite + frontend `test:studio` + `tsc`.

---

## 9. Rollout

### 9.1. Phase 0 — đã implement

1. Phân vai theo median pitch của từng source line; rewrite role voice 1/2/3/4.
2. Bass dùng `Chord.bass_midi` fold vào 40..53.
3. Mid fold chord tone vào 50..65.
4. Bump revision khi note thực tế đổi (hiện là 7).
5. Render lại cùng figure pool, nghe thử bass/mid/lead.

**Dừng ở đây để user nghe.** Chỉ làm Phase 1 nếu Phase 0 ổn.

### 9.2. Phase 1

1. Thêm schema `line_eighth` + context arrays.
2. Implement `price / MA5 / MA20` sau một flag/option:
   ```text
   VSTOCK_STUDIO_LINES=price_ma5_ma20
   ```
   hoặc request field `lines`.
3. So sánh output với Phase 0 trên cùng figure pool:
   - nghe 3 bè;
   - xem MusicXML;
   - kiểm tra average ordering.
4. Nếu ổn, bật default cho `studio_piece + villa`.
5. Giữ legacy không đổi.

---

## 10. Rủi ro / câu hỏi mở

0. **Voice number gốc không phải role** — file hiện tại có bass ở voice 2.
   → Phase 0 phân vai theo median pitch của từng source line rồi rewrite role
   voice 1-1, nên giữ duration và tránh overlap.
1. **Sustained bass bị cắt** nếu phân vai lại ở từng onset.
   → Phân vai theo source line, không theo onset; có test bass giữ duration.
2. **Support collapse về voice 2** khi hai source voice cùng vào support.
   → Rewrite support role voice thành 2/4 ngay khi bind.
3. **MA5/MA20 tương quan** trong thị trường đi ngang; mid/bass có thể chụm.
   → band + chord quantize + soft warning.
4. **MA20 trên 1M thật quá dài** (~21 daily closes).
   → window config; sau này adaptive theo range.
5. **Bass theo MA20 nhưng harmony đổi nhanh**.
   → bass vẫn ưu tiên root/fifth của chord; MA20 chỉ quyết định contour/register.
6. **Voice order mềm có thể nghe lạ** ở vài bar.
   → chấp nhận warning; không hard reject.
7. **Guitar hand span** có thể buộc bỏ note mid.
   → `_repair` chạy sau cùng; warning nếu drop.
8. **Line arrays làm tăng kích thước cache**.
   → hash theo config + series; line arrays chỉ runtime, không lưu vào source spec.

---

## 11. Chốt

### Phase 0 — đã implement

```text
Role = pitch order (lead voice1, lowest non-lead bass, rest mid)
Bass = Chord.bass_midi folded to 40..53
Mid  = chord tone folded to 50..65
Lead = price melody, 59..81
Scope = StudioPiece + villa only
Legacy = unchanged
Revision = 5
```

Sau Phase 0: user nghe thử, kiểm tra bass đã xuống đúng octave chưa, rồi quyết
định có làm Phase 1 không.

### Phase 1 — deferred

```text
Lead = price
Mid  = MA5
Bass = MA20
Quantize = nearest chord tone in register band
Ordering = soft average, warning only
Revision = 6
```

Chưa implement Phase 1 trong tài liệu này.
