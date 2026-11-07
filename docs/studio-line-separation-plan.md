# Kế hoạch: tách bè Lead / Mid / Bass theo Price / MA5 / MA20

Trạng thái: **thiết kế, chưa implement**.  
Phạm vi: `release/studio-v2.1`, chỉ Render Piece / luồng Studio pattern mới.  
Đối tượng áp dụng: ensemble `villa` (Villa-Lobos) và các piece tạo từ `StudioPiece`; **không** áp dụng cho legacy render.

Tài liệu liên quan:

- `docs/studio-render-piece-plan.md` — Render Piece, plan/tag/series.
- `docs/studio-schottish-pattern-plan.md` — pattern production.
- `backend/app/studio/render_piece.py` — rebind pitch hiện tại.
- `backend/app/studio/texture_resolve.py` — resolve `PitchRef`.
- `backend/app/sonify/studio_piece.py` — arrangement / authored cell.

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

Mục tiêu của thay đổi này là tách **ba đường độc lập** nhưng vẫn nằm trong
harmony của bar.

---

## 2. Quyết định thiết kế

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

Đề xuất band mặc định (có overlap nhẹ):

```text
bass:  40..55   (E2..G3)
mid:   55..67   (G3..G4)
lead:  64..83   (E4..B5)
```

Band này chỉ là **target**, không phải hard validation. Guitar playability
(`_repair`, hand span, fret) vẫn là cổng cuối.

### 4.5. Quantize vào harmony

Với mỗi line/bar:

1. normalize giá trị line về `[0, 1]` theo min/max của chính line đó;
2. map vào register band của voice;
3. chọn chord tone gần nhất trong band;
4. bass ưu tiên root/fifth; mid ưu tiên 3rd/5th/7th; lead ưu tiên chord tone
   hoặc scale tone gần nhất.

Không dùng `chord_degree(2)` / `chord_root` cố định nữa cho mid/bass trong
luồng mới.

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

Đề xuất bump:

```python
STUDIO_RENDER_REVISION = 3
```

Lý do: cùng một request cũ có thể trả MusicXML/WAV khác sau khi thay đổi
line policy. Không bump sẽ khiến cache cũ che mất thay đổi.

---

## 8. Test plan

### 8.1. Unit

- `MA5` / `MA20` trên series ngắn, warmup đúng, không zero-pad.
- `line_eighth` shift theo `bind_texture` khi tile sang bar khác.
- `resolve_pitch`:
  - line đúng;
  - eighth ngoài range raise;
  - line thiếu raise.
- Quantize: mọi note non-cadence thuộc chord của bar.
- Register band:
  - bass trong 40..55;
  - mid trong 55..67;
  - lead trong 64..83;
  - không vượt guitar ceiling.

### 8.2. Integration

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

1. Thêm schema `line_eighth` + context arrays, chưa bật cho mọi piece.
2. Implement `price / MA5 / MA20` sau một flag/option:
   ```text
   VSTOCK_STUDIO_LINES=price_ma5_ma20
   ```
   hoặc request field `lines`.
3. So sánh output với bản cũ trên cùng figure pool:
   - nghe 3 bè;
   - xem MusicXML;
   - kiểm tra average ordering.
4. Nếu ổn, bật default cho `studio_piece + villa`.
5. Giữ legacy không đổi.

---

## 10. Rủi ro / câu hỏi mở

1. **MA5/MA20 tương quan** trong thị trường đi ngang; mid/bass có thể chụm.
   → band + chord quantize + soft warning.
2. **MA20 trên 1M thật quá dài** (~21 daily closes).
   → window config; sau này adaptive theo range.
3. **Bass theo MA20 nhưng harmony đổi nhanh**.
   → bass vẫn ưu tiên root/fifth của chord; MA20 chỉ quyết định contour/register.
4. **Voice order mềm có thể nghe lạ** ở vài bar.
   → chấp nhận warning; không hard reject.
5. **Guitar hand span** có thể buộc bỏ note mid.
   → `_repair` chạy sau cùng; warning nếu drop.
6. **Line arrays làm tăng kích thước cache**.
   → hash theo config + series; line arrays chỉ runtime, không lưu vào source spec.

---

## 11. Chốt

Thiết kế được chốt ở mức MVP:

```text
Lead = price
Mid  = MA5
Bass = MA20
Quantize = nearest chord tone in register band
Ordering = soft average, warning only
Scope = StudioPiece + villa only
Legacy = unchanged
```

Chưa implement trong tài liệu này. Bước tiếp theo là thêm `line_eighth`, line
context, và bật thử `price / MA5 / MA20` sau flag.
